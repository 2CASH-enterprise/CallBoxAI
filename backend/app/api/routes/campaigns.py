"""
Endpoints Campagnes d'appels sortants (section 13 du cahier des charges).

MVP : le traitement d'un lot d'appels est déclenché manuellement via
/run-batch plutôt qu'automatiquement par un worker asynchrone (Celery n'est
pas encore branché — voir section 40 et le docker-compose.yml). Le
comportement métier (statuts, retry, horaires) est le même ; seul le
déclenchement change une fois Celery en place.
"""
import logging
import random
import uuid
from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

logger = logging.getLogger(__name__)
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_organization_access
from app.core.call_pipeline import execute_mock_call
from app.core.contacts_import import import_contacts_from_csv_text
from app.core.compliance import check_compliance
from app.models.campaign import Campaign, CampaignTarget
from app.models.contact import Contact
from app.models.agent import Agent
from app.models.call import Call
from app.providers.telephony.mock import MockTelephonyProvider
from app.providers.voice.mock import MockVoiceProvider
from app.providers.embeddings.mock import MockEmbeddingProvider
from app.providers.analytics.mock import MockAnalyticsProvider

router = APIRouter()

# Toujours Mock, volontairement (même raisonnement que /calls — section 40) :
# le traitement de campagne simule des issues variées (répondu/pas de
# réponse/échec) et ne doit jamais dépendre d'un vrai provider, qui ne
# pourrait pas produire ces résultats synchrones.
telephony_provider = MockTelephonyProvider()
voice_provider = MockVoiceProvider()
embedding_provider = MockEmbeddingProvider()
analytics_provider = MockAnalyticsProvider()

DEFAULT_BATCH_SIZE = 10

# Délai minimum avant de rappeler un contact déjà joint mais pas encore
# converti (relance basée sur l'intérêt, section 13) — évite de le rappeler
# deux fois dans la même minute, ce qui n'aurait aucun sens commercialement.
FOLLOW_UP_DELAY_DAYS = 2


# ---------- Schémas ----------

class CampaignCreate(BaseModel):
    name: str
    agent_id: uuid.UUID
    schedule_start: str = "08:00"
    schedule_end: str = "19:00"
    max_attempts: int = 3
    max_follow_ups: int = 2
    target_market: str | None = None


class CampaignOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    agent_id: uuid.UUID
    name: str
    status: str
    schedule_start: str
    schedule_end: str
    max_attempts: int
    max_follow_ups: int
    target_market: str | None
    created_at: datetime
    started_at: datetime | None

    class Config:
        from_attributes = True


class CampaignStats(BaseModel):
    total: int
    pending: int
    completed: int
    no_answer: int
    failed: int


class CampaignDetailOut(CampaignOut):
    stats: CampaignStats


class ImportSummary(BaseModel):
    imported: int
    skipped_invalid_phone: int
    total_targets: int


class BatchResult(BaseModel):
    processed: int
    completed: int
    no_answer: int
    failed: int
    follow_up_scheduled: int
    blocked_compliance: int = 0
    message: str | None = None


# ---------- Aides ----------

def get_campaign_or_404(campaign_id: uuid.UUID, organization_id: uuid.UUID, db: Session) -> Campaign:
    campaign = (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.organization_id == organization_id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campagne introuvable pour cette organisation")
    return campaign


def compute_stats(campaign_id: uuid.UUID, db: Session) -> CampaignStats:
    targets = db.query(CampaignTarget).filter(CampaignTarget.campaign_id == campaign_id).all()
    return CampaignStats(
        total=len(targets),
        pending=sum(1 for t in targets if t.status == "pending"),
        completed=sum(1 for t in targets if t.status == "completed"),
        no_answer=sum(1 for t in targets if t.status == "no_answer"),
        failed=sum(1 for t in targets if t.status == "failed"),
    )


def within_schedule(campaign: Campaign, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    start = time.fromisoformat(campaign.schedule_start)
    end = time.fromisoformat(campaign.schedule_end)
    current = now.time()
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end  # fenêtre à cheval sur minuit


def _needs_follow_up(qualification: str | None, action_taken: str | None, follow_up_count: int, max_follow_ups: int) -> bool:
    """
    Décide si un contact JOINT doit être rappelé plus tard (relance) plutôt
    que considéré comme définitivement traité — basé sur l'intérêt exprimé,
    pas seulement la joignabilité (section 13/19).
    """
    if action_taken == "Rendez-vous pris":
        return False  # converti : terminé
    if qualification in ("Pas intéressé", "À suivre par un humain"):
        return False  # refus définitif, ou pris en charge par un humain
    # "Prospect chaud"/"Prospect tiède" sans rendez-vous encore -> relance possible
    return follow_up_count < max_follow_ups


# ---------- Endpoints ----------

@router.post("/campaigns", response_model=CampaignOut)
def create_campaign(
    payload: CampaignCreate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    agent = db.query(Agent).filter(Agent.id == payload.agent_id, Agent.organization_id == organization_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent introuvable pour cette organisation")

    campaign = Campaign(organization_id=organization_id, **payload.model_dump())
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


@router.get("/campaigns", response_model=list[CampaignOut])
def list_campaigns(
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    return db.query(Campaign).filter(Campaign.organization_id == organization_id).all()


@router.get("/campaigns/{campaign_id}", response_model=CampaignDetailOut)
def get_campaign(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    campaign = get_campaign_or_404(campaign_id, organization_id, db)
    stats = compute_stats(campaign.id, db)
    return CampaignDetailOut(**CampaignOut.model_validate(campaign).model_dump(), stats=stats)


@router.post("/campaigns/{campaign_id}/import", response_model=ImportSummary)
async def import_contacts(
    campaign_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Import CSV (section 13) : colonnes attendues `phone` (obligatoire),
    `first_name`, `last_name` (optionnelles). Les numéros invalides sont
    comptabilisés et ignorés plutôt que de faire échouer tout l'import.
    Les contacts sont créés (ou réutilisés s'ils existent déjà par numéro)
    dans le CRM de l'organisation (section 18), via l'utilitaire partagé
    avec l'import CRM direct (app.core.contacts_import).
    """
    campaign = get_campaign_or_404(campaign_id, organization_id, db)

    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    shared_summary, contacts = import_contacts_from_csv_text(db, organization_id, raw)

    for contact in contacts:
        db.add(CampaignTarget(campaign_id=campaign.id, contact_id=contact.id))

    db.commit()
    total_targets = db.query(CampaignTarget).filter(CampaignTarget.campaign_id == campaign.id).count()
    return ImportSummary(
        imported=shared_summary.imported,
        skipped_invalid_phone=shared_summary.skipped_invalid_phone,
        total_targets=total_targets,
    )


@router.post("/campaigns/{campaign_id}/start", response_model=CampaignOut)
def start_campaign(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    campaign = get_campaign_or_404(campaign_id, organization_id, db)
    if campaign.status == "completed":
        raise HTTPException(status_code=400, detail="Cette campagne est déjà terminée")
    campaign.status = "running"
    if not campaign.started_at:
        campaign.started_at = datetime.utcnow()
    db.commit()
    db.refresh(campaign)
    return campaign


@router.post("/campaigns/{campaign_id}/pause", response_model=CampaignOut)
def pause_campaign(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    campaign = get_campaign_or_404(campaign_id, organization_id, db)
    campaign.status = "paused"
    db.commit()
    db.refresh(campaign)
    return campaign


@router.post("/campaigns/{campaign_id}/run-batch", response_model=BatchResult)
def run_batch(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Traite un lot de contacts en attente (jusqu'à DEFAULT_BATCH_SIZE).
    En production, ce traitement serait déclenché automatiquement par un
    worker Celery respectant la concurrence et les horaires en continu — ici,
    un appel manuel simule un "tour" de la campagne (section 13 et 14).
    """
    campaign = get_campaign_or_404(campaign_id, organization_id, db)

    if campaign.status != "running":
        return BatchResult(processed=0, completed=0, no_answer=0, failed=0, follow_up_scheduled=0, message="La campagne n'est pas en cours (démarrez-la d'abord).")

    if not within_schedule(campaign):
        return BatchResult(
            processed=0, completed=0, no_answer=0, failed=0, follow_up_scheduled=0,
            message=f"Hors horaires autorisés ({campaign.schedule_start} - {campaign.schedule_end}).",
        )

    agent = db.query(Agent).filter(Agent.id == campaign.agent_id).first()

    now = datetime.utcnow()
    targets = (
        db.query(CampaignTarget)
        .filter(
            CampaignTarget.campaign_id == campaign.id,
            CampaignTarget.status == "pending",
            or_(CampaignTarget.next_attempt_at.is_(None), CampaignTarget.next_attempt_at <= now),
        )
        .limit(DEFAULT_BATCH_SIZE)
        .all()
    )

    completed_count = 0
    no_answer_count = 0
    failed_count = 0
    follow_up_count_total = 0
    blocked_compliance_count = 0

    for target in targets:
        contact = db.query(Contact).filter(Contact.id == target.contact_id).first()

        # Compliance Check (section 42/43) : verrou AVANT de composer le
        # numéro — ni consommé comme tentative, ni marqué en échec, juste
        # laissé "pending" pour être retenté plus tard (les horaires se
        # résolvent d'eux-mêmes ; le consentement, dès qu'il sera enregistré).
        allowed, reason = check_compliance(
            db, organization_id, campaign.target_market, agent, contact.id, now,
        )
        if not allowed:
            logger.info("Contact %s bloqué par le Compliance Check : %s", contact.id, reason)
            blocked_compliance_count += 1
            continue

        target.attempts += 1

        # Simulation d'un résultat d'appel varié (mode Mock, section 40.3) :
        # 70% répondu, 20% pas de réponse (retry possible), 10% échec.
        outcome = random.choices(["completed", "no_answer", "failed"], weights=[70, 20, 10])[0]

        if outcome == "completed":
            call = execute_mock_call(
                db=db,
                organization_id=organization_id,
                agent=agent,
                to_number=contact.phone,
                from_number="+221780000000",
                telephony_provider=telephony_provider,
                voice_provider=voice_provider,
                embedding_provider=embedding_provider,
                analytics_provider=analytics_provider,
                direction="outbound",
                contact_id=contact.id,
            )
            target.call_id = call.id
            completed_count += 1

            if _needs_follow_up(call.qualification, call.action_taken, target.follow_up_count, campaign.max_follow_ups):
                target.follow_up_count += 1
                target.status = "pending"
                target.next_attempt_at = now + timedelta(days=FOLLOW_UP_DELAY_DAYS)
                follow_up_count_total += 1
            else:
                target.status = "completed"
        elif target.attempts >= campaign.max_attempts:
            target.status = "failed"
            failed_count += 1
        else:
            target.status = "pending"  # retenté au prochain lot (retry, section 13)
            no_answer_count += 1

    remaining_pending = db.query(CampaignTarget).filter(
        CampaignTarget.campaign_id == campaign.id, CampaignTarget.status == "pending"
    ).count()
    if remaining_pending == 0 and len(targets) > 0:
        campaign.status = "completed"

    db.commit()

    return BatchResult(
        processed=len(targets),
        completed=completed_count,
        no_answer=no_answer_count,
        failed=failed_count,
        follow_up_scheduled=follow_up_count_total,
        blocked_compliance=blocked_compliance_count,
        message="Aucun contact en attente." if not targets else None,
    )
