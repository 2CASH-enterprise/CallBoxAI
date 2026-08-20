"""
Interface abstraite PMSProvider (section 5 du cahier des charges) — système
de gestion hôtelière (Property Management System). Aucune logique métier ne
doit dépendre directement d'un PMS particulier (Mews, Cloudbeds, Opera...) :
elle ne doit connaître que cette interface.
"""
from abc import ABC, abstractmethod
from datetime import date


class PMSProvider(ABC):
    @abstractmethod
    def check_availability(self, check_in: date, check_out: date, room_type: str | None = None) -> list[dict]:
        """
        Retourne les offres disponibles pour la période demandée : liste de
        dicts {room_type, rate_per_night, total_price, rooms_available, currency}.
        """
        ...

    @abstractmethod
    def create_reservation(
        self, check_in: date, check_out: date, room_type: str, guest_name: str, guest_phone: str, num_guests: int = 1
    ) -> dict:
        """
        Crée la réservation côté PMS. Retourne un dict avec au minimum
        confirmation_number, status, rate_per_night, total_price.
        Lève ValueError si aucune disponibilité pour cette demande.
        """
        ...

    @abstractmethod
    def cancel_reservation(self, confirmation_number: str) -> dict:
        ...

    @abstractmethod
    def modify_reservation(
        self, confirmation_number: str, check_in: date, check_out: date, room_type: str
    ) -> dict:
        """
        Modifie les dates et/ou le type de chambre d'une réservation
        existante. Retourne un dict avec confirmation_number, status,
        rate_per_night, total_price (mis à jour). Lève ValueError si
        aucune disponibilité pour les nouvelles dates/type demandés.
        """
        ...
