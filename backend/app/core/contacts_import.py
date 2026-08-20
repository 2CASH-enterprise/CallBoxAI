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


class ImportSummary(BaseModel):
    imported: int
    skipped_invalid_phone: int
    total: int


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


def import_contacts_from_csv_text(db: Session, organization_id: uuid.UUID, csv_text: str) -> tuple[ImportSummary, list[Contact]]:
    """
    Parse un texte CSV et crée (ou réutilise, par numéro) les contacts
    correspondants pour cette organisation. Les numéros invalides sont
    comptabilisés et ignorés plutôt que de faire échouer tout l'import
    (utile pour une liste de 1000 contacts avec quelques erreurs de saisie).
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    fieldnames = reader.fieldnames or []

    phone_col = _find_column(fieldnames, PHONE_COLUMN_ALIASES) or "phone"
    first_name_col = _find_column(fieldnames, FIRST_NAME_COLUMN_ALIASES)
    last_name_col = _find_column(fieldnames, LAST_NAME_COLUMN_ALIASES)
    email_col = _find_column(fieldnames, EMAIL_COLUMN_ALIASES)

    imported = 0
    skipped = 0
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
            )
            db.add(contact)
            db.flush()

        contacts.append(contact)
        imported += 1

    summary = ImportSummary(imported=imported, skipped_invalid_phone=skipped, total=imported + skipped)
    return summary, contacts
