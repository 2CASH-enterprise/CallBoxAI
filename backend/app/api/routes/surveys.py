"""
Endpoints Sondages téléphoniques. Réutilise le pipeline d'appel partagé
(app.core.call_pipeline) : chaque appel de sondage est un vrai Call, visible
normalement dans le CRM/Analytics, avec en plus des réponses structurées.
"""
import json
import random
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_organization_access
from app.core.call_pipeline import execute_mock_call
from app.models.survey import Survey, SurveyResponse
from app.models.agent import Agent
from app.models.contact import Contact
from app.providers.telephony.mock import MockTelephonyProvider
from app.providers.voice.mock import MockVoiceProvider
from app.providers.embeddings.mock import MockEmbeddingProvider
from app.providers.analytics.mock import MockAnalyticsProvider

router = APIRouter()

# Toujours Mock, volontairement — mêmes raisons que /calls et /campaigns
# (section 40) : simulation du pipeline, pas un vrai appel synchrone.
telephony_provider = MockTelephonyProvider()
voice_provider = MockVoiceProvider()
embedding_provider = MockEmbeddingProvider()
analytics_provider = MockAnalyticsProvider()


# ---------- Schémas ----------

class QuestionIn(BaseModel):
    id: str
    text: str
    type: Literal["choice", "rating", "open"]
    options: list[str] | None = None


class SurveyCreate(BaseModel):
    title: str
    agent_id: uuid.UUID
    questions: list[QuestionIn]


class SurveyOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    agent_id: uuid.UUID
    title: str
    questions: list[QuestionIn]
    created_at: datetime


class SurveyResponseOut(BaseModel):
    id: uuid.UUID
    survey_id: uuid.UUID
    contact_id: uuid.UUID | None
    call_id: uuid.UUID | None
    answers: dict
    created_at: datetime


class CallSurveyRequest(BaseModel):
    contact_id: uuid.UUID
    to_number: str


class QuestionResult(BaseModel):
    question_id: str
    question_text: str
    type: str
    # choice : {option: count} ; rating : {"average": x, "count": n} ; open : liste de réponses (20 max)
    summary: dict


class SurveyResultsOut(BaseModel):
    survey_id: uuid.UUID
    total_responses: int
    results: list[QuestionResult]


# ---------- Aides ----------

def _get_survey_or_404(survey_id: uuid.UUID, organization_id: uuid.UUID, db: Session) -> Survey:
    survey = db.query(Survey).filter(Survey.id == survey_id, Survey.organization_id == organization_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Sondage introuvable pour cette organisation")
    return survey


def _to_survey_out(survey: Survey) -> SurveyOut:
    return SurveyOut(
        id=survey.id,
        organization_id=survey.organization_id,
        agent_id=survey.agent_id,
        title=survey.title,
        questions=[QuestionIn(**q) for q in json.loads(survey.questions)],
        created_at=survey.created_at,
    )


def _generate_mock_answer(question: dict):
    """
    Simule la réponse collectée pendant l'appel (section 40.3) — à remplacer
    par l'extraction réelle depuis la conversation une fois un vrai LLM branché.
    """
    if question["type"] == "choice":
        return random.choice(question.get("options") or ["Oui", "Non"])
    if question["type"] == "rating":
        return random.randint(1, 5)
    return random.choice([
        "Très satisfait du service.",
        "Rien à signaler de particulier.",
        "Pourrait être amélioré sur les délais.",
        "Excellent accueil, merci.",
    ])


# ---------- Endpoints ----------

@router.post("/surveys", response_model=SurveyOut)
def create_survey(
    payload: SurveyCreate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    if not payload.questions:
        raise HTTPException(status_code=400, detail="Le sondage doit contenir au moins une question")
    for q in payload.questions:
        if q.type == "choice" and not q.options:
            raise HTTPException(status_code=400, detail=f"La question « {q.text} » de type choix doit avoir des options")

    agent = db.query(Agent).filter(Agent.id == payload.agent_id, Agent.organization_id == organization_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent introuvable pour cette organisation")

    survey = Survey(
        organization_id=organization_id,
        agent_id=payload.agent_id,
        title=payload.title,
        questions=json.dumps([q.model_dump() for q in payload.questions]),
    )
    db.add(survey)
    db.commit()
    db.refresh(survey)
    return _to_survey_out(survey)


@router.get("/surveys", response_model=list[SurveyOut])
def list_surveys(
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    surveys = db.query(Survey).filter(Survey.organization_id == organization_id).all()
    return [_to_survey_out(s) for s in surveys]


@router.get("/surveys/{survey_id}", response_model=SurveyOut)
def get_survey(
    survey_id: uuid.UUID,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    return _to_survey_out(_get_survey_or_404(survey_id, organization_id, db))


@router.post("/surveys/{survey_id}/call", response_model=SurveyResponseOut)
def call_for_survey(
    survey_id: uuid.UUID,
    payload: CallSurveyRequest,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Simule un appel de sondage à un contact : déclenche un vrai appel via le
    pipeline partagé (visible normalement dans Appels/Analytics/CRM), et
    enregistre des réponses structurées au questionnaire.
    """
    survey = _get_survey_or_404(survey_id, organization_id, db)
    agent = db.query(Agent).filter(Agent.id == survey.agent_id).first()
    contact = db.query(Contact).filter(
        Contact.id == payload.contact_id, Contact.organization_id == organization_id
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact introuvable pour cette organisation")

    call = execute_mock_call(
        db=db,
        organization_id=organization_id,
        agent=agent,
        to_number=payload.to_number,
        from_number="+221780000000",
        telephony_provider=telephony_provider,
        voice_provider=voice_provider,
        embedding_provider=embedding_provider,
        analytics_provider=analytics_provider,
        direction="outbound",
        contact_id=contact.id,
    )

    questions = json.loads(survey.questions)
    answers = {q["id"]: _generate_mock_answer(q) for q in questions}

    response = SurveyResponse(
        organization_id=organization_id,
        survey_id=survey.id,
        contact_id=contact.id,
        call_id=call.id,
        answers=json.dumps(answers),
    )
    db.add(response)
    db.commit()
    db.refresh(response)

    return SurveyResponseOut(
        id=response.id, survey_id=response.survey_id, contact_id=response.contact_id,
        call_id=response.call_id, answers=answers, created_at=response.created_at,
    )


@router.get("/surveys/{survey_id}/results", response_model=SurveyResultsOut)
def get_survey_results(
    survey_id: uuid.UUID,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    survey = _get_survey_or_404(survey_id, organization_id, db)
    questions = json.loads(survey.questions)
    responses = db.query(SurveyResponse).filter(SurveyResponse.survey_id == survey.id).all()
    parsed_answers = [json.loads(r.answers) for r in responses]

    results = []
    for q in questions:
        qid = q["id"]
        values = [a.get(qid) for a in parsed_answers if a.get(qid) is not None]

        if q["type"] == "choice":
            summary = {opt: values.count(opt) for opt in (q.get("options") or [])}
        elif q["type"] == "rating":
            summary = {"average": round(sum(values) / len(values), 2) if values else 0, "count": len(values)}
        else:
            summary = {"responses": values[-20:]}

        results.append(QuestionResult(question_id=qid, question_text=q["text"], type=q["type"], summary=summary))

    return SurveyResultsOut(survey_id=survey.id, total_responses=len(responses), results=results)
