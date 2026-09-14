"""
Compliance Check (section 42/43 du cahier des charges) — verrou technique
appliqué AVANT de déclencher un appel sortant, selon le marché ciblé par la
campagne. Centralise les règles légales par marché à un seul endroit,
plutôt que dispersées dans les prompts (une nouvelle règle découverte
s'ajoute ici, jamais agent par agent).

Règles confirmées à ce jour (voir échanges avec l'utilisateur) :
- France : depuis le 11 août 2026, le B2C exige un consentement préalable
  explicite (fin du régime Bloctel/opposition) ; le B2B reste sous
  "intérêt légitime", pas de consentement requis. Horaires de démarchage
  encadrés (retenus ici : lundi-vendredi, 10h-20h — à affiner si une source
  plus précise est trouvée).
- Côte d'Ivoire : Loi n°2013-450, pas d'exigence de consentement préalable
  spécifique au B2C identifiée à ce jour ; aucune restriction d'horaires
  confirmée. Profil volontairement permissif tant que non précisé.
- Marché non renseigné (target_market=None) : aucune règle appliquée —
  résilience (section 29), on ne bloque jamais sur une règle qu'on n'a pas
  encore modélisée.
"""
from datetime import datetime, time

# Modèles considérés B2C — qualification en cascade se terminant par la
# transmission d'un lead à un commercial humain, jamais de RDV réservé par
# l'IA (contrairement au B2B). Le consentement préalable ne concerne que ces
# catégories, jamais la prospection B2B ("intérêt légitime").
B2C_STYLE_TEMPLATES = {"prospection_b2c", "reactivation", "upsell", "cross_sell"}

MARKET_COMPLIANCE_RULES = {
    "france": {
        "requires_consent_for_b2c": True,
        "calling_hours_start": time(10, 0),
        "calling_hours_end": time(20, 0),
        "calling_days": {0, 1, 2, 3, 4},  # lundi(0) à vendredi(4)
    },
    "cote_ivoire": {
        "requires_consent_for_b2c": False,
        "calling_hours_start": None,
        "calling_hours_end": None,
        "calling_days": None,
    },
}


def check_compliance(
    db,
    organization_id,
    target_market: str | None,
    agent,
    contact_id,
    now: datetime | None = None,
    campaign_id=None,
) -> tuple[bool, str | None]:
    """
    Retourne (autorisé, motif_si_bloqué). Ne bloque QUE sur une règle
    explicitement modélisée pour le marché ciblé — jamais par défaut.
    Écrit systématiquement une ligne dans le journal d'audit (section
    42/43), autorisé ou bloqué, pour reconstruire après coup "pourquoi cet
    appel a été autorisé".
    """
    now = now or datetime.utcnow()

    # Liste repoussoir (section 42/43) : vérifiée EN PREMIER, indépendamment
    # du marché — une personne ayant explicitement demandé à ne plus être
    # rappelée ne doit JAMAIS être recontactée, peu importe la campagne.
    from app.models.contact import Contact

    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if contact and contact.do_not_call:
        _log_compliance_decision(
            db, organization_id, contact_id, campaign_id, "blocked",
            "Contact sur liste repoussoir (opposition explicite).", None,
        )
        return False, "Ce contact a demandé à ne plus être recontacté (liste repoussoir)."

    rules = MARKET_COMPLIANCE_RULES.get(target_market) if target_market else None
    is_b2c_style = agent.source_template in B2C_STYLE_TEMPLATES
    legal_basis = "consentement (B2C)" if is_b2c_style else "intérêt légitime (B2B)"

    if not rules:
        _log_compliance_decision(db, organization_id, contact_id, campaign_id, "allowed", "Marché non modélisé — aucune règle appliquée.", legal_basis)
        return True, None

    # Horaires légaux de démarchage, s'ils sont définis pour ce marché
    if rules["calling_hours_start"] is not None:
        if rules["calling_days"] is not None and now.weekday() not in rules["calling_days"]:
            reason = f"Hors des jours de démarchage autorisés pour le marché '{target_market}'."
            _log_compliance_decision(db, organization_id, contact_id, campaign_id, "blocked", reason, legal_basis)
            return False, reason
        if not (rules["calling_hours_start"] <= now.time() <= rules["calling_hours_end"]):
            reason = f"Hors des horaires de démarchage autorisés pour le marché '{target_market}'."
            _log_compliance_decision(db, organization_id, contact_id, campaign_id, "blocked", reason, legal_basis)
            return False, reason

    # Consentement préalable obligatoire, uniquement pour un agent B2C sur un marché qui l'exige
    if rules["requires_consent_for_b2c"] and is_b2c_style:
        from app.api.routes.consent import has_valid_consent

        if not has_valid_consent(db, organization_id, contact_id):
            reason = f"Consentement préalable requis et absent (marché '{target_market}', agent B2C)."
            _log_compliance_decision(db, organization_id, contact_id, campaign_id, "blocked", reason, legal_basis)
            return False, reason

    _log_compliance_decision(db, organization_id, contact_id, campaign_id, "allowed", "Toutes les conditions requises sont réunies.", legal_basis)
    return True, None


def _log_compliance_decision(db, organization_id, contact_id, campaign_id, decision, reason, legal_basis) -> None:
    """
    Résilience (section 29) : un échec d'écriture du journal d'audit ne doit
    JAMAIS empêcher la décision de conformité elle-même de s'appliquer.
    """
    from app.models.compliance_audit_log import ComplianceAuditLog

    try:
        db.add(ComplianceAuditLog(
            organization_id=organization_id, contact_id=contact_id, campaign_id=campaign_id,
            decision=decision, reason=reason, legal_basis=legal_basis,
        ))
        db.commit()
    except Exception:
        db.rollback()
