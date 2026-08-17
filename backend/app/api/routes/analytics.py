"""
Endpoints Analytics (section 19 du cahier des charges).
"""
import uuid
from collections import Counter

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_organization_access
from app.models.call import Call
from app.models.agent import Agent

router = APIRouter(prefix="/analytics", tags=["analytics"])


class BreakdownItem(BaseModel):
    label: str
    count: int


class AgentPerformance(BaseModel):
    agent_id: uuid.UUID
    agent_name: str
    calls_count: int
    avg_score: float | None


class AnalyticsSummary(BaseModel):
    total_calls: int
    avg_score: float | None
    qualification_rate: float  # % d'appels "Prospect chaud" ou "Prospect tiède"
    appointment_rate: float  # % d'appels ayant abouti à un rendez-vous
    transfer_rate: float  # % d'appels transférés à un humain
    by_intent: list[BreakdownItem]
    by_qualification: list[BreakdownItem]
    by_sentiment: list[BreakdownItem]
    by_agent: list[AgentPerformance]


def _rate(count: int, total: int) -> float:
    return round(100 * count / total, 1) if total else 0.0


@router.get("/summary", response_model=AnalyticsSummary)
def analytics_summary(
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    calls = db.query(Call).filter(Call.organization_id == organization_id).all()
    total = len(calls)

    scores = [c.score for c in calls if c.score is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else None

    qualified = sum(1 for c in calls if c.qualification in ("Prospect chaud", "Prospect tiède"))
    appointments = sum(1 for c in calls if c.action_taken == "Rendez-vous pris")
    transferred = sum(1 for c in calls if c.status == "transferred")

    intent_counts = Counter(c.intent for c in calls if c.intent)
    qualification_counts = Counter(c.qualification for c in calls if c.qualification)
    sentiment_counts = Counter(c.sentiment for c in calls if c.sentiment)

    agents = db.query(Agent).filter(Agent.organization_id == organization_id).all()
    by_agent = []
    for agent in agents:
        agent_calls = [c for c in calls if c.agent_id == agent.id]
        if not agent_calls:
            continue
        agent_scores = [c.score for c in agent_calls if c.score is not None]
        by_agent.append(
            AgentPerformance(
                agent_id=agent.id,
                agent_name=agent.name,
                calls_count=len(agent_calls),
                avg_score=round(sum(agent_scores) / len(agent_scores), 1) if agent_scores else None,
            )
        )

    return AnalyticsSummary(
        total_calls=total,
        avg_score=avg_score,
        qualification_rate=_rate(qualified, total),
        appointment_rate=_rate(appointments, total),
        transfer_rate=_rate(transferred, total),
        by_intent=[BreakdownItem(label=k, count=v) for k, v in intent_counts.most_common()],
        by_qualification=[BreakdownItem(label=k, count=v) for k, v in qualification_counts.most_common()],
        by_sentiment=[BreakdownItem(label=k, count=v) for k, v in sentiment_counts.most_common()],
        by_agent=sorted(by_agent, key=lambda a: a.calls_count, reverse=True),
    )
