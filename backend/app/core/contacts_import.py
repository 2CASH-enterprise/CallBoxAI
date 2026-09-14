"""
Import en masse de contacts CRM (section 18 du cahier des charges), partagé
entre l'import direct dans le CRM et l'import de contacts pour une campagne
(section 13). Accepte du texte CSV, que ce texte vienne d'un fichier uploadé
ou d'un simple copier-coller.

Tolérant aux variations réelles des fichiers export (Google Maps, annuaires,
tableurs) : reconnaît plusieurs noms de colonnes courants, et nettoie les
numéros de téléphone formatés (espaces, tirets, parenthèses) avant validation.
"""
import csv
import io
import re
import unicodedata
import uuid

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.contact import Contact

PHONE_REGEX = re.compile(r"^\+?[0-9]{8,15}$")

# Caractères de mise en forme courants dans les numéros exportés
# (ex. "+33 1 78 90 78 10", "+33-1-78-90-78-10") — retirés avant validation.
_PHONE_FORMATTING_CHARS = re.compile(r"[\s\-.()]")

# Plusieurs noms de colonnes acceptés pour chaque champ (insensible à la
# casse et aux accents) — un export français utilise souvent "telephone" ou
# "nom" plutôt que "phone"/"first_name".
PHONE_COLUMN_ALIASES = {"phone", "telephone", "tel", "numero", "num", "mobile", "numero_de_telephone"}
FIRST_NAME_COLUMN_ALIASES = {"first_name", "firstname", "prenom", "nom", "name"}
LAST_NAME_COLUMN_ALIASES = {"last_name", "lastname", "nom_de_famille"}
EMAIL_COLUMN_ALIASES = {"email", "mail", "courriel", "e-mail"}

# Champs enrichis B2B (section 42/43) : traçabilité de la donnée, utile
# pour documenter la base légale d'une campagne de prospection entreprises.
COMPANY_COLUMN_ALIASES = {"company", "societe", "société", "entreprise"}
JOB_TITLE_COLUMN_ALIASES = {"job_title", "fonction", "poste", "titre"}
SOURCE_COLUMN_ALIASES = {"source", "provenance", "origine"}


class ImportSummary(BaseModel):
    imported: int
    skipped_invalid_phone: int
    total: int
    already_do_not_call: int = 0  # informatif : jamais bloqués à l'import, seulement au moment de l'appel
    consent_certified_count: int = 0  # nombre de contacts pour lesquels un consentement a été certifié à l'import


def _normalize_header(header: str) -> str:
    """Insensible à la casse et aux accents : "Téléphone" == "telephone"."""
    normalized = unicodedata.normalize("NFKD", header).encode("ascii", "ignore").decode("ascii")
    return normalized.strip().lower().replace(" ", "_")


def _find_column(fieldnames: list[str], aliases: set[str]) -> str | None:
    normalized_map = {_normalize_header(f): f for f in fieldnames}
    for alias in aliases:
        if alias in normalized_map:
            return normalized_map[alias]
    return None


def _clean_phone(raw: str) -> str:
    """Retire les espaces/tirets/points/parenthèses d'un numéro formaté."""
    return _PHONE_FORMATTING_CHARS.sub("", raw.strip())


def import_contacts_from_csv_text(
    db: Session,
    organization_id: uuid.UUID,
    csv_text: str,
    certify_consent: bool = False,
    consent_note: str | None = None,
) -> tuple[ImportSummary, list[Contact]]:
    """
    Parse un texte CSV et crée (ou réutilise, par numéro) les contacts
    correspondants pour cette organisation. Les numéros invalides sont
    comptabilisés et ignorés plutôt que de faire échouer tout l'import
    (utile pour une liste de 1000 contacts avec quelques erreurs de saisie).

    `certify_consent` (section 42/43) : à utiliser quand le client importe
    des personnes pour lesquelles il DÉCLARE disposer déjà d'un consentement
    valide (ex. clients existants pour une campagne de Fidélisation, pas
    capturés via un formulaire comme Facebook Lead Ads) — crée une entrée
    dans le Consent Ledger pour chaque contact du fichier, marquée
    explicitement comme une DÉCLARATION du client, jamais une preuve
    vérifiée indépendamment par la plateforme (honnêteté de la source,
    importante en cas de contrôle).
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    fieldnames = reader.fieldnames or []

    phone_col = _find_column(fieldnames, PHONE_COLUMN_ALIASES) or "phone"
    first_name_col = _find_column(fieldnames, FIRST_NAME_COLUMN_ALIASES)
    last_name_col = _find_column(fieldnames, LAST_NAME_COLUMN_ALIASES)
    email_col = _find_column(fieldnames, EMAIL_COLUMN_ALIASES)
    company_col = _find_column(fieldnames, COMPANY_COLUMN_ALIASES)
    job_title_col = _find_column(fieldnames, JOB_TITLE_COLUMN_ALIASES)
    source_col = _find_column(fieldnames, SOURCE_COLUMN_ALIASES)

    imported = 0
    skipped = 0
    already_do_not_call = 0
    consent_certified_count = 0
    contacts: list[Contact] = []

    for row in reader:
        phone = _clean_phone(row.get(phone_col) or "")
        if not PHONE_REGEX.match(phone):
            skipped += 1
            continue

        contact = db.query(Contact).filter(
            Contact.organization_id == organization_id, Contact.phone == phone
        ).first()
        if not contact:
            contact = Contact(
                organization_id=organization_id,
                phone=phone,
                first_name=(row.get(first_name_col) or "").strip() or None if first_name_col else None,
                last_name=(row.get(last_name_col) or "").strip() or None if last_name_col else None,
                email=(row.get(email_col) or "").strip() or None if email_col else None,
                company=(row.get(company_col) or "").strip() or None if company_col else None,
                job_title=(row.get(job_title_col) or "").strip() or None if job_title_col else None,
                source=(row.get(source_col) or "").strip() or None if source_col else None,
            )
            db.add(contact)
            db.flush()

        if contact.do_not_call:
            already_do_not_call += 1

        if certify_consent:
            from app.models.consent_record import ConsentRecord

            text = "Consentement DÉCLARÉ par le client au moment de l'import (fichier CSV), non capturé directement par la plateforme."
            if consent_note:
                text += f" Précision fournie par le client : {consent_note}"
            db.add(ConsentRecord(
                organization_id=organization_id, contact_id=contact.id,
                source="import_certifie_client", consent_text=text,
            ))
            consent_certified_count += 1

        contacts.append(contact)
        imported += 1

    summary = ImportSummary(
        imported=imported, skipped_invalid_phone=skipped, total=imported + skipped,
        already_do_not_call=already_do_not_call, consent_certified_count=consent_certified_count,
    )
    return summary, contacts
