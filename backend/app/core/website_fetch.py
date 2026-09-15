"""
Récupération et nettoyage du contenu d'un site web (outil interne de
prospection) — transforme une page HTML brute en texte lisible, avant
extraction par un modèle de langage.
"""
import httpx
from bs4 import BeautifulSoup

# En-têtes proches d'un vrai navigateur (section 29, résilience) : de
# nombreux sites (hôtels notamment, souvent derrière Cloudflare ou une
# protection similaire) renvoient une erreur 403 face à un User-Agent qui
# s'identifie explicitement comme un robot, même parfaitement légitime.
# Utilisé uniquement pour consulter des pages publiques, une seule requête
# par cible — usage ponctuel et raisonnable, pas une exploration en masse.
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


def fetch_website_text(url: str, timeout: float = 10.0) -> str:
    """
    Retourne le texte visible de la page (scripts/styles retirés). Lève une
    exception en cas d'échec — à la charge de l'appelant de la traiter
    (résilience, section 29) : une analyse ratée ne doit jamais bloquer le
    reste du lot de cibles.
    """
    response = httpx.get(
        url, timeout=timeout, follow_redirects=True,
        headers=REQUEST_HEADERS,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned
