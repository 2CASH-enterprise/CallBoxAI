"""
Sondages téléphoniques (section 12/19 du cahier des charges élargi).
Les questions sont stockées en JSON (texte) — voir la note dans
app/models/knowledge.py sur ce choix, cohérent avec le reste du projet.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Text

from app.core.database import Base
from app.models.distributor import GUID


class Survey(Base):
    __tablename__ = "surveys"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)
    agent_id = Column(GUID(), ForeignKey("agents.id"), nullable=False)

    title = Column(String, nullable=False)
    questions = Column(Text, nullable=False)  # JSON : liste de {id, text, type, options?}

    created_at = Column(DateTime, default=datetime.utcnow)


class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)
    survey_id = Column(GUID(), ForeignKey("surveys.id"), nullable=False)
    contact_id = Column(GUID(), ForeignKey("contacts.id"), nullable=True)
    call_id = Column(GUID(), ForeignKey("calls.id"), nullable=True)

    answers = Column(Text, nullable=False)  # JSON : {question_id: réponse}

    created_at = Column(DateTime, default=datetime.utcnow)
