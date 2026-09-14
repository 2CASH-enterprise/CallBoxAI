"""
Génération du document PDF lisible du droit d'accès (section 42/43 du
cahier des charges) — à remettre directement à la personne qui exerce ce
droit, contrairement à l'export JSON brut (usage technique/programmatique).
"""
import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def _format_date(iso_string: str | None) -> str:
    if not iso_string:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_string)
        return dt.strftime("%d/%m/%Y à %H:%M")
    except ValueError:
        return iso_string


def generate_data_export_pdf(export: dict, organization_name: str) -> bytes:
    """Construit le PDF à partir des données déjà compilées (voir _compile_contact_export)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=20 * mm, bottomMargin=20 * mm, leftMargin=20 * mm, rightMargin=20 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleCustom", parent=styles["Title"], fontSize=18, spaceAfter=4)
    section_style = ParagraphStyle("SectionCustom", parent=styles["Heading2"], fontSize=13, spaceBefore=16, spaceAfter=6, textColor=colors.HexColor("#12151F"))
    body_style = ParagraphStyle("BodyCustom", parent=styles["Normal"], fontSize=9.5, leading=13)
    muted_style = ParagraphStyle("MutedCustom", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#64687A"))

    contact = export["contact"]
    story = []

    story.append(Paragraph("Vos données personnelles", title_style))
    story.append(Paragraph(
        f"Document généré le {datetime.utcnow().strftime('%d/%m/%Y à %H:%M')} UTC, en réponse à votre demande "
        f"d'exercice du droit d'accès auprès de {organization_name}.",
        muted_style,
    ))
    story.append(Spacer(1, 10))

    # ---------- Informations de contact ----------
    story.append(Paragraph("Vos informations", section_style))
    contact_rows = [
        ["Nom", f"{contact.get('first_name') or ''} {contact.get('last_name') or ''}".strip() or "—"],
        ["Téléphone", contact.get("phone") or "—"],
        ["Email", contact.get("email") or "—"],
        ["Entreprise", contact.get("company") or "—"],
        ["Fonction", contact.get("job_title") or "—"],
        ["Statut", contact.get("status") or "—"],
        ["Enregistré depuis le", _format_date(contact.get("created_at"))],
    ]
    table = Table(contact_rows, colWidths=[120, 340])
    table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#64687A")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#E1E3DC")),
    ]))
    story.append(table)

    # ---------- Appels ----------
    story.append(Paragraph("Historique de vos appels", section_style))
    calls = export.get("calls", [])
    if not calls:
        story.append(Paragraph("Aucun appel enregistré.", body_style))
    else:
        for c in calls:
            direction_label = "Appel entrant (vous nous avez appelés)" if c["direction"] == "inbound" else "Appel sortant (nous vous avons appelés)"
            duration_min = round((c.get("duration_seconds") or 0) / 60, 1)
            story.append(Paragraph(f"<b>{_format_date(c['started_at'])}</b> — {direction_label}, {duration_min} min", body_style))
            if c.get("qualification"):
                story.append(Paragraph(f"Résultat : {c['qualification']}", muted_style))
            if c.get("summary"):
                story.append(Paragraph(f"Résumé : {c['summary']}", muted_style))
            story.append(Spacer(1, 6))

    # ---------- Rendez-vous ----------
    if export.get("appointments"):
        story.append(Paragraph("Vos rendez-vous", section_style))
        for a in export["appointments"]:
            story.append(Paragraph(f"{_format_date(a['scheduled_at'])} — statut : {a['status']}", body_style))

    # ---------- Tickets ----------
    if export.get("tickets"):
        story.append(Paragraph("Vos demandes de support", section_style))
        for t in export["tickets"]:
            story.append(Paragraph(f"{_format_date(t['created_at'])} — {t['subject']} (statut : {t['status']})", body_style))

    # ---------- Consentements ----------
    if export.get("consent_records"):
        story.append(Paragraph("Historique de votre consentement", section_style))
        for c in export["consent_records"]:
            status = "Retiré" if c.get("revoked_at") else "Actif"
            story.append(Paragraph(f"{_format_date(c['consented_at'])} — source : {c['source']} — statut : {status}", body_style))
            story.append(Paragraph(c["consent_text"], muted_style))
            story.append(Spacer(1, 6))

    # ---------- Journal de conformité ----------
    if export.get("compliance_audit_logs"):
        story.append(Paragraph("Journal des vérifications avant chaque appel", section_style))
        for a in export["compliance_audit_logs"]:
            decision_label = "Autorisé" if a["decision"] == "allowed" else "Bloqué"
            story.append(Paragraph(f"{_format_date(a['created_at'])} — {decision_label} — {a['reason']}", muted_style))

    # ---------- Messages ----------
    if export.get("whatsapp_messages") or export.get("sms_messages"):
        story.append(Paragraph("Messages reçus (WhatsApp / SMS)", section_style))
        for m in export.get("whatsapp_messages", []):
            story.append(Paragraph(f"{_format_date(m['created_at'])} (WhatsApp) — {m['body']}", muted_style))
        for m in export.get("sms_messages", []):
            story.append(Paragraph(f"{_format_date(m['created_at'])} (SMS) — {m['body']}", muted_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
