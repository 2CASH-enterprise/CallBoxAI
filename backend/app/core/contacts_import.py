"""
Import en masse de contacts CRM (section 18 du cahier des charges), partagé
entre l'import direct dans le CRM et l'import de contacts pour une campagne
(section 13). Accepte du texte CSV (colonnes phone/first_name/last_name),
que ce texte vienne d'un fichier uploadé ou d'un simple copier-coller.
"""
import csv
import io
import re
import uuid

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.contact import Contact

PHONE_REGEX = re.compile(r"^\+?[0-9]{8,15}$")


class ImportSummary(BaseModel):
    imported: int
    skipped_invalid_phone: int
    total: int


def import_contacts_from_csv_text(db: Session, organization_id: uuid.UUID, csv_text: str) -> tuple[ImportSummary, list[Contact]]:
    """
    Parse un texte CSV et crée (ou réutilise, par numéro) les contacts
    correspondants pour cette organisation. Les numéros invalides sont
    comptabilisés et ignorés plutôt que de faire échouer tout l'import
    (utile pour une liste de 1000 contacts avec quelques erreurs de saisie).
    """
    reader = csv.DictReader(io.StringIO(csv_text))

    imported = 0
    skipped = 0
    contacts: list[Contact] = []

    for row in reader:
        phone = (row.get("phone") or "").strip()
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
                first_name=(row.get("first_name") or "").strip() or None,
                last_name=(row.get("last_name") or "").strip() or None,
            )
            db.add(contact)
            db.flush()

        contacts.append(contact)
        imported += 1

    summary = ImportSummary(imported=imported, skipped_invalid_phone=skipped, total=imported + skipped)
    return summary, contacts
