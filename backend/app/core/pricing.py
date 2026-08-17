"""
Placeholder de tarification MVP (sections 20-21 du cahier des charges).

En attendant le vrai moteur de billing configurable (abonnement / usage /
performance), on simule un chiffre d'affaires à partir d'un prix fixe par
appel. Utilisé à la fois par le module Distributeur (calcul de commissions)
et le Dashboard Super Admin (revenu estimé de la plateforme).
"""
MOCK_PRICE_PER_CALL_FCFA = 500.0
