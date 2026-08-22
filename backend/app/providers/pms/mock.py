"""
MockPMSProvider — simule un système de gestion hôtelière sans compte ni
connecteur réel (section 40.3). La disponibilité est calculée de façon
déterministe (fonction de hachage sur la date et le type de chambre) plutôt
que purement aléatoire : une même demande donne toujours le même résultat,
ce qui rend le comportement testable et prévisible pour une démo.

À remplacer par un vrai connecteur (Mews, Cloudbeds...) une fois un hôtel
cible identifié, sans changer le reste du pipeline (section 5 et 16).
"""
import hashlib
import uuid
from datetime import date

from app.providers.pms.base import PMSProvider

# Catalogue de démonstration — en production, ces données viendraient du PMS
# réel (inventaire, tarifs dynamiques par date, etc.).
ROOM_CATALOG = [
    {"room_type": "Chambre Standard", "rate_per_night": 89.0, "total_rooms": 10},
    {"room_type": "Chambre Supérieure", "rate_per_night": 129.0, "total_rooms": 6},
    {"room_type": "Suite", "rate_per_night": 219.0, "total_rooms": 2},
]


def _deterministic_availability(check_in: date, room_type: str, total_rooms: int) -> int:
    """
    Nombre de chambres disponibles, déterminé par un hachage de la date et du
    type de chambre — toujours le même résultat pour une même demande
    (contrairement à un tirage aléatoire), tout en variant selon la date et
    le type pour rester réaliste en démo. Le modulo (total_rooms + 1) permet
    d'atteindre toute valeur de 0 à total_rooms, y compris pour un petit
    inventaire (ex. 2 suites) — un simple ratio proportionnel arrondi
    n'atteindrait jamais 0 dans ce cas.
    """
    seed = f"{check_in.isoformat()}-{room_type}"
    digest = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
    return digest % (total_rooms + 1)


class MockPMSProvider(PMSProvider):
    def check_availability(self, check_in: date, check_out: date, room_type: str | None = None) -> list[dict]:
        if check_in < date.today():
            raise ValueError("La date d'arrivée ne peut pas être dans le passé")
        nights = (check_out - check_in).days
        if nights <= 0:
            raise ValueError("La date de départ doit être après la date d'arrivée")

        offers = []
        for room in ROOM_CATALOG:
            if room_type and room["room_type"] != room_type:
                continue
            rooms_available = _deterministic_availability(check_in, room["room_type"], room["total_rooms"])
            if rooms_available <= 0:
                continue
            offers.append({
                "room_type": room["room_type"],
                "rate_per_night": room["rate_per_night"],
                "total_price": round(room["rate_per_night"] * nights, 2),
                "rooms_available": rooms_available,
                "currency": "EUR",
            })
        return offers

    def create_reservation(
        self, check_in: date, check_out: date, room_type: str, guest_name: str, guest_phone: str, num_guests: int = 1
    ) -> dict:
        offers = self.check_availability(check_in, check_out, room_type)
        if not offers:
            raise ValueError(f"Aucune disponibilité pour « {room_type} » du {check_in} au {check_out}")

        offer = offers[0]
        return {
            "confirmation_number": f"MOCK-{uuid.uuid4().hex[:8].upper()}",
            "status": "confirmed",
            "room_type": room_type,
            "rate_per_night": offer["rate_per_night"],
            "total_price": offer["total_price"],
            "currency": offer["currency"],
        }

    def cancel_reservation(self, confirmation_number: str) -> dict:
        return {"confirmation_number": confirmation_number, "status": "cancelled"}

    def modify_reservation(self, confirmation_number: str, check_in: date, check_out: date, room_type: str) -> dict:
        offers = self.check_availability(check_in, check_out, room_type)
        if not offers:
            raise ValueError(f"Aucune disponibilité pour « {room_type} » du {check_in} au {check_out}")

        offer = offers[0]
        return {
            "confirmation_number": confirmation_number,
            "status": "confirmed",
            "room_type": room_type,
            "rate_per_night": offer["rate_per_night"],
            "total_price": offer["total_price"],
            "currency": offer["currency"],
        }
