import unicodedata


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return stripped.lower().replace("đ", "d").replace("Ä‘", "d")
