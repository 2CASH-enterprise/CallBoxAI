"""
Découpage de texte en chunks (section 10 du cahier des charges).
"""


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """
    Découpe un texte en morceaux d'environ `chunk_size` caractères, avec un
    recouvrement (`overlap`) pour ne pas perdre le contexte à la frontière
    entre deux chunks. Les coupures sont ajustées au plus proche espace pour
    éviter de couper un mot en deux.
    """
    text = text.strip()
    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))

        if end < len(text):
            last_space = text.rfind(" ", start, end)
            if last_space > start:
                end = last_space

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break
        start = max(end - overlap, start + 1)

    return chunks
