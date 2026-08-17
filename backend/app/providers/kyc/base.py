"""
Interface abstraite KYCProvider (section 41.5 du cahier des charges).
"""
from abc import ABC, abstractmethod


class KYCProvider(ABC):
    @abstractmethod
    def verify_identity_document(self, document_url: str) -> dict:
        ...

    @abstractmethod
    def liveness_check(self, selfie_url: str) -> dict:
        ...

    @abstractmethod
    def check_sanctions_list(self, full_name: str) -> dict:
        ...

    @abstractmethod
    def get_verification_status(self, dossier_id: str) -> dict:
        ...


class ManualReviewProvider(KYCProvider):
    """
    Implémentation MVP : tout dossier passe en revue humaine (back-office),
    sans fournisseur eKYC payant (cohérent avec la section 40).
    """

    def verify_identity_document(self, document_url: str) -> dict:
        return {"status": "pending_manual_review"}

    def liveness_check(self, selfie_url: str) -> dict:
        return {"status": "pending_manual_review"}

    def check_sanctions_list(self, full_name: str) -> dict:
        return {"status": "not_checked_automatically", "note": "à valider manuellement en MVP"}

    def get_verification_status(self, dossier_id: str) -> dict:
        return {"dossier_id": dossier_id, "status": "under_review"}
