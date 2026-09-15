"""
Outil interne de prospection Super Admin (section stratégie de croissance —
jamais visible des clients). Générique par secteur : une campagne cible un
secteur (hôtellerie aujourd'hui, centres de formation/cabinets médicaux
demain) et propose le modèle d'agent adapté à un lot de cibles.

Étape 1/N du chantier : socle (campagne, import de cibles). Les étapes
suivantes (analyse de site, création d'agent, page de démo, email) viendront
s'ajouter à ce même modèle, sans le reconstruire.
"""
import csv
import io
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_super_admin
from app.models.user import User
from app.models.prospecting_campaign import ProspectingCampaign, ProspectingTarget, TARGET_STATUSES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/prospecting-campaigns", tags=["prospecting-campaigns"])

MAX_TARGETS_PER_CAMPAIGN = 50

# Alias de colonnes reconnus à l'import — pensés pour accepter directement
# l'export Atout France (NOM COMMERCIAL, ADRESSE, SITE INTERNET...) sans
# renommage manuel préalable.
COMPANY_NAME_ALIASES = {"company_name", "nom", "nom_commercial", "établissement", "etablissement"}
ADDRESS_ALIASES = {"address", "adresse"}
PHONE_ALIASES = {"phone", "telephone", "téléphone"}
WEBSITE_ALIASES = {"website_url", "site_internet", "site internet", "website", "site_web"}
EMAIL_ALIASES = {"email", "mail"}
CONTACT_NAME_ALIASES = {"contact_name", "directeur", "contact", "propriétaire", "proprietaire"}


def _find_column(fieldnames: list[str], aliases: set[str]) -> str | None:
    normalized = {f.strip().lower().replace(" ", "_"): f for f in fieldnames}
    normalized_aliases = {a.replace(" ", "_") for a in aliases}
    for alias in normalized_aliases:
        if alias in normalized:
            return normalized[alias]
    return None


class CampaignCreate(BaseModel):
    name: str
    sector: str
    agent_template_key: str


class CampaignOut(BaseModel):
    id: uuid.UUID
    name: str
    sector: str
    agent_template_key: str
    created_at: datetime
    targets_count: int = 0

    class Config:
        from_attributes = True


class TargetOut(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    company_name: str
    address: str | None
    phone: str | None
    website_url: str | None
    email: str | None
    contact_name: str | None
    status: str
    extracted_info: str | None
    demo_agent_id: uuid.UUID | None
    demo_page_slug: str | None
    email_subject: str | None
    email_body: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class TargetUpdate(BaseModel):
    company_name: str | None = None
    address: str | None = None
    phone: str | None = None
    website_url: str | None = None
    email: str | None = None
    contact_name: str | None = None
    status: str | None = None
    extracted_info: str | None = None
    email_subject: str | None = None
    email_body: str | None = None


class ImportSummary(BaseModel):
    imported: int
    skipped: int
    total_in_campaign: int


def _to_campaign_out(campaign: ProspectingCampaign, targets_count: int) -> CampaignOut:
    return CampaignOut(
        id=campaign.id, name=campaign.name, sector=campaign.sector,
        agent_template_key=campaign.agent_template_key, created_at=campaign.created_at,
        targets_count=targets_count,
    )


@router.post("", response_model=CampaignOut)
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db), _admin: User = Depends(require_super_admin)):
    campaign = ProspectingCampaign(**payload.model_dump())
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return _to_campaign_out(campaign, targets_count=0)


@router.get("", response_model=list[CampaignOut])
def list_campaigns(db: Session = Depends(get_db), _admin: User = Depends(require_super_admin)):
    campaigns = db.query(ProspectingCampaign).order_by(ProspectingCampaign.created_at.desc()).all()
    results = []
    for c in campaigns:
        count = db.query(ProspectingTarget).filter(ProspectingTarget.campaign_id == c.id).count()
        results.append(_to_campaign_out(c, targets_count=count))
    return results


@router.get("/{campaign_id}/targets", response_model=list[TargetOut])
def list_targets(campaign_id: uuid.UUID, db: Session = Depends(get_db), _admin: User = Depends(require_super_admin)):
    campaign = db.query(ProspectingCampaign).filter(ProspectingCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campagne introuvable")
    return db.query(ProspectingTarget).filter(ProspectingTarget.campaign_id == campaign_id).order_by(ProspectingTarget.created_at).all()


@router.post("/{campaign_id}/import", response_model=ImportSummary)
async def import_targets(
    campaign_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
):
    """
    Import CSV d'un lot de cibles — plafonné à 50 par campagne (décision
    validée avec l'utilisateur), pour rester gérable avec la vérification
    humaine à chaque étape du parcours.
    """
    campaign = db.query(ProspectingCampaign).filter(ProspectingCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campagne introuvable")

    existing_count = db.query(ProspectingTarget).filter(ProspectingTarget.campaign_id == campaign_id).count()
    if existing_count >= MAX_TARGETS_PER_CAMPAIGN:
        raise HTTPException(status_code=400, detail=f"Cette campagne a déjà atteint la limite de {MAX_TARGETS_PER_CAMPAIGN} cibles.")

    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    fieldnames = reader.fieldnames or []

    company_col = _find_column(fieldnames, COMPANY_NAME_ALIASES)
    if not company_col:
        raise HTTPException(status_code=400, detail="Colonne du nom d'établissement introuvable dans le fichier.")
    address_col = _find_column(fieldnames, ADDRESS_ALIASES)
    phone_col = _find_column(fieldnames, PHONE_ALIASES)
    website_col = _find_column(fieldnames, WEBSITE_ALIASES)
    email_col = _find_column(fieldnames, EMAIL_ALIASES)
    contact_col = _find_column(fieldnames, CONTACT_NAME_ALIASES)

    imported = 0
    skipped = 0
    remaining_capacity = MAX_TARGETS_PER_CAMPAIGN - existing_count

    for row in reader:
        if imported >= remaining_capacity:
            skipped += 1
            continue
        name = (row.get(company_col) or "").strip()
        if not name:
            skipped += 1
            continue

        db.add(ProspectingTarget(
            campaign_id=campaign_id,
            company_name=name,
            address=(row.get(address_col) or "").strip() or None if address_col else None,
            phone=(row.get(phone_col) or "").strip() or None if phone_col else None,
            website_url=(row.get(website_col) or "").strip() or None if website_col else None,
            email=(row.get(email_col) or "").strip() or None if email_col else None,
            contact_name=(row.get(contact_col) or "").strip() or None if contact_col else None,
        ))
        imported += 1

    db.commit()
    total = db.query(ProspectingTarget).filter(ProspectingTarget.campaign_id == campaign_id).count()
    return ImportSummary(imported=imported, skipped=skipped, total_in_campaign=total)


@router.patch("/{campaign_id}/targets/{target_id}", response_model=TargetOut)
def update_target(
    campaign_id: uuid.UUID,
    target_id: uuid.UUID,
    payload: TargetUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
):
    """
    Édition manuelle d'une cible — sert notamment à la vérification humaine
    (relecture/correction des informations extraites avant l'envoi).
    """
    target = db.query(ProspectingTarget).filter(
        ProspectingTarget.id == target_id, ProspectingTarget.campaign_id == campaign_id
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="Cible introuvable pour cette campagne")

    updates = payload.model_dump(exclude_unset=True)
    if "status" in updates and updates["status"] is not None and updates["status"] not in TARGET_STATUSES:
        raise HTTPException(status_code=400, detail=f"Statut invalide (attendu parmi : {', '.join(TARGET_STATUSES)})")

    for field, value in updates.items():
        setattr(target, field, value)

    db.commit()
    db.refresh(target)
    return target


def _get_analysis_provider():
    """
    Résilience (section 29) : sans aucune clé API configurée, on retombe sur
    le fournisseur simulé plutôt que planter. Mistral priorisé (préférence
    exprimée par l'utilisateur, souveraineté française/européenne) si les
    deux clés sont configurées — sinon Anthropic, sinon simulé.
    """
    from app.core.config import settings

    if settings.mistral_api_key:
        from app.providers.analysis.mistral_provider import MistralWebsiteAnalysisProvider

        return MistralWebsiteAnalysisProvider(api_key=settings.mistral_api_key)

    if settings.anthropic_api_key:
        from app.providers.analysis.anthropic_provider import AnthropicWebsiteAnalysisProvider

        return AnthropicWebsiteAnalysisProvider(api_key=settings.anthropic_api_key)

    from app.providers.analysis.mock import MockWebsiteAnalysisProvider

    return MockWebsiteAnalysisProvider()


def _analyze_single_target(db: Session, target: ProspectingTarget) -> tuple[bool, str]:
    """
    Retourne (succès, message). Ne lève jamais d'exception — pensé pour être
    appelé en boucle sur tout un lot sans qu'une cible en échec n'interrompe
    les suivantes (section 29).
    """
    if not target.website_url:
        return False, "Aucun site web renseigné pour cette cible."

    from app.core.website_fetch import fetch_website_text

    try:
        website_text = fetch_website_text(target.website_url)
    except Exception as exc:
        logger.warning("Échec de récupération du site %s : %s", target.website_url, exc)
        return False, f"Site injoignable ou erreur de récupération ({exc})."

    if not website_text.strip():
        return False, "Aucun contenu textuel exploitable trouvé sur le site."

    try:
        provider = _get_analysis_provider()
        extracted = provider.extract_practical_info(website_text, target.company_name)
    except Exception as exc:
        logger.exception("Échec de l'extraction pour la cible %s", target.id)
        return False, f"Échec de l'analyse par le modèle de langage ({exc})."

    target.extracted_info = extracted
    target.status = "analyzed"
    db.commit()
    return True, "Analyse terminée."


@router.post("/{campaign_id}/targets/{target_id}/analyze")
def analyze_target(
    campaign_id: uuid.UUID,
    target_id: uuid.UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
):
    """Déclenche (ou relance) l'analyse automatique du site web pour UNE cible précise."""
    target = db.query(ProspectingTarget).filter(
        ProspectingTarget.id == target_id, ProspectingTarget.campaign_id == campaign_id
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="Cible introuvable pour cette campagne")

    success, message = _analyze_single_target(db, target)
    return {"success": success, "message": message}


class BulkAnalyzeResult(BaseModel):
    analyzed: int
    failed: int
    details: list[dict]


@router.post("/{campaign_id}/analyze-all", response_model=BulkAnalyzeResult)
def analyze_all_targets(campaign_id: uuid.UUID, db: Session = Depends(get_db), _admin: User = Depends(require_super_admin)):
    """
    Analyse toutes les cibles de la campagne pas encore analysées — une
    cible en échec (site injoignable, pas de site renseigné...) n'interrompt
    jamais les suivantes du lot.
    """
    campaign = db.query(ProspectingCampaign).filter(ProspectingCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campagne introuvable")

    targets = db.query(ProspectingTarget).filter(
        ProspectingTarget.campaign_id == campaign_id, ProspectingTarget.status == "imported"
    ).all()

    analyzed, failed = 0, 0
    details = []
    for target in targets:
        success, message = _analyze_single_target(db, target)
        details.append({"target_id": str(target.id), "company_name": target.company_name, "success": success, "message": message})
        if success:
            analyzed += 1
        else:
            failed += 1

    return BulkAnalyzeResult(analyzed=analyzed, failed=failed, details=details)
