import re
import unicodedata


TARGET_TERMS = (
    "brazil",
    "brasil",
    "remote",
    "remoto",
    "latam",
    "latin america",
    "américa latina",
    "anywhere",
    "worldwide",
    "americas",
    "Maranhão",
    "MA",
    "Piauí",
    "PI",
    "Ceará",
    "CE",
    "Rio Grande do Norte",
    "RN",
    "Paraíba",
    "PB",
    "Pernambuco",
    "PE",
    "Alagoas",
    "AL",
    "Sergipe",
    "SE",
    "Bahia",
    "BA",
    "São Luís",
    "Teresina",
    "Fortaleza",
    "Natal",
    "João Pessoa",
    "Recife",
    "Maceió",
    "Aracaju",
    "Salvador",
    "Campina Grande",
    "Caruaru",
    "Petrolina",
    "Juazeiro",
    "Feira de Santana",
    "Vitória da Conquista",
    "Imperatriz",
    "Mossoró",
    "Sobral",
    "Juazeiro do Norte",
    "Barreiras",
    "Ilhéus",
    "Itabuna",
    "Parnaíba",
    "Crato",
    "Garanhuns",
    "São Paulo",
    "Rio de Janeiro",
    "Belo Horizonte",
    "Curitiba",
    "Porto Alegre",
    "Florianópolis",
    "Brasília",
)


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _flatten_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten_text(item) for item in value)
    return ""


_TARGET_PATTERN = re.compile(
    r"(?<!\w)(?:"
    + "|".join(
        re.escape(_normalize_text(term))
        for term in sorted(TARGET_TERMS, key=len, reverse=True)
    )
    + r")(?!\w)"
)


def matches_target_scope(*values: object) -> bool:
    text = _normalize_text(" ".join(_flatten_text(value) for value in values))
    return bool(_TARGET_PATTERN.search(text))
