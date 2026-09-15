"""
Récupération et nettoyage du contenu d'un site web (outil interne de
prospection) — transforme une page HTML brute en texte lisible, avant
extraction par un modèle de langage.
"""
import httpx
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; CallBoxAI-Prospecting/1.0; +https://callbox-ai.com)"


def fetch_website_text(url: str, timeout: float = 10.0) -> str:
    """
    Retourne le texte visible de la page (scripts/styles retirés). Lève une
    exception en cas d'échec — à la charge de l'appelant de la traiter
    (résilience, section 29) : une analyse ratée ne doit jamais bloquer le
    reste du lot de cibles.
    """
    response = httpx.get(
        url, timeout=timeout, follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned
