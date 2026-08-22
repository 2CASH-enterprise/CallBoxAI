"""
Modèles d'email (section 12/16 du cahier des charges). Personnalisation au
nom de l'ÉTABLISSEMENT CLIENT (Organization.name) — à ne pas confondre avec
la marque blanche des distributeurs (app.core / Distributor.brand_name), qui
concerne l'apparence du DASHBOARD, pas les communications envoyées aux
clients finaux de l'établissement.
"""
from datetime import datetime


def reservation_confirmation_html(
    hotel_name: str,
    confirmation_number: str,
    room_type: str,
    check_in: datetime,
    check_out: datetime,
    nights: int,
    notes: str | None = None,
) -> str:
    notes_block = (
        f'<p style="margin:0 0 24px 0;color:#64687A;font-size:14px;line-height:1.6;">{notes}</p>'
        if notes else ""
    )
    return f"""\
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background-color:#F4F5F1;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#F4F5F1;padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;background-color:#FFFFFF;border-radius:12px;overflow:hidden;border:1px solid #E1E3DC;">
          <tr>
            <td style="background-color:#0D1220;padding:28px 32px;">
              <span style="color:#FFFFFF;font-size:19px;font-weight:600;letter-spacing:-0.01em;">{hotel_name}</span>
            </td>
          </tr>
          <tr>
            <td style="padding:32px;">
              <p style="margin:0 0 4px 0;color:#12B886;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;">Réservation confirmée</p>
              <h1 style="margin:0 0 24px 0;color:#12151F;font-size:22px;font-weight:600;letter-spacing:-0.01em;">Merci pour votre réservation !</h1>

              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#F4F5F1;border-radius:10px;margin-bottom:24px;">
                <tr>
                  <td style="padding:20px 24px;">
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                      <tr><td style="padding:6px 0;color:#64687A;font-size:13px;">Numéro de confirmation</td><td align="right" style="padding:6px 0;color:#12151F;font-size:13px;font-weight:600;font-family:monospace;">{confirmation_number}</td></tr>
                      <tr><td style="padding:6px 0;color:#64687A;font-size:13px;">Type de chambre</td><td align="right" style="padding:6px 0;color:#12151F;font-size:13px;font-weight:600;">{room_type}</td></tr>
                      <tr><td style="padding:6px 0;color:#64687A;font-size:13px;">Arrivée</td><td align="right" style="padding:6px 0;color:#12151F;font-size:13px;font-weight:600;">{check_in:%d/%m/%Y}</td></tr>
                      <tr><td style="padding:6px 0;color:#64687A;font-size:13px;">Départ</td><td align="right" style="padding:6px 0;color:#12151F;font-size:13px;font-weight:600;">{check_out:%d/%m/%Y}</td></tr>
                      <tr><td style="padding:6px 0;color:#64687A;font-size:13px;">Nombre de nuits</td><td align="right" style="padding:6px 0;color:#12151F;font-size:13px;font-weight:600;">{nights}</td></tr>
                    </table>
                  </td>
                </tr>
              </table>

              {notes_block}
              <p style="margin:0;color:#64687A;font-size:14px;line-height:1.6;">Au plaisir de vous accueillir bientôt.</p>
            </td>
          </tr>
          <tr>
            <td style="padding:20px 32px;border-top:1px solid #E1E3DC;">
              <p style="margin:0;color:#9BA1AE;font-size:11px;">{hotel_name} — cette confirmation a été générée automatiquement.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def reservation_confirmation_text(
    hotel_name: str,
    confirmation_number: str,
    room_type: str,
    check_in: datetime,
    check_out: datetime,
    nights: int,
    notes: str | None = None,
) -> str:
    """Version texte brut — secours pour les clients mail sans support HTML."""
    return (
        f"{hotel_name}\n\n"
        f"Votre réservation est confirmée.\n\n"
        f"Numéro de confirmation : {confirmation_number}\n"
        f"Type de chambre : {room_type}\n"
        f"Arrivée : {check_in:%d/%m/%Y}\n"
        f"Départ : {check_out:%d/%m/%Y}\n"
        f"Nombre de nuits : {nights}\n\n"
        f"{notes or ''}\n\n"
        f"Au plaisir de vous accueillir bientôt."
    )
