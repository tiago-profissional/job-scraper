import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from scraper.models.job import NormalizedJob
from scraper.fetching.http_client import check_url_alive, is_github_issue_open

ALLOWED_DOMAINS = {
    "adzuna": ("adzuna.com.br",),
    "remotive": ("remotive.com",),
    "arbeitnow": ("*",),  # "*" permite qualquer domínio HTTP/HTTPS válido vindo da Arbeitnow
}

# O formato do caminho de uma vaga individual para cada fonte
JOB_PATH_PATTERNS = {
    "adzuna": re.compile(r"^/details/\d+/?$"),
}

MIN_DESCRIPTION_LENGTH = 50

BLOCKED_PATH_SEGMENTS = {
    "login_page": {"login", "signin", "entrar"},
    "search_page": {"search", "busca"},
}

GENERIC_TITLES = {"vagas", "jobs", "resultados", "search results"}


def _domain_allowed(host: str, allowed: tuple[str, ...]) -> bool:
    if "*" in allowed:
        return True
    return any(host == d or host.endswith("." + d) for d in allowed)


def _check_page_type(source: str, path: str) -> list[str]:
    """Rejeita páginas de login, busca e outras que não sejam uma vaga individual."""
    segments = set(path.lower().strip("/").split("/")) if path else set()

    blocked = [
        reason
        for reason, words in BLOCKED_PATH_SEGMENTS.items()
        if segments & words
    ]
    if blocked:
        return blocked

    pattern = JOB_PATH_PATTERNS.get(source)
    if pattern and not pattern.match(path):
        return ["not_a_job_page"]
    return []


def validate_job(job: NormalizedJob) -> list[str]:
    """Retorna os motivos de rejeição de uma vaga. Lista vazia indica vaga válida."""
    reasons = []

    if not job.title:
        reasons.append("missing_title")
    elif job.title.strip().lower() in GENERIC_TITLES:
        reasons.append("generic_title")

    if not job.company:
        reasons.append("missing_company")

    if not job.description:
        reasons.append("missing_description")
    elif len(job.description) < MIN_DESCRIPTION_LENGTH:
        reasons.append("description_too_short")

    url = str(job.source_url) if job.source_url else ""
    parts = urlsplit(url)
    allowed = ALLOWED_DOMAINS.get(job.source)

    if not url:
        reasons.append("missing_url")
    elif parts.scheme not in ("http", "https") or not parts.hostname:
        reasons.append("invalid_url")
    elif allowed is None:
        reasons.append("source_not_allowed")
    elif not _domain_allowed(parts.hostname, allowed):
        reasons.append("domain_not_allowed")
    else:
        reasons.extend(_check_page_type(job.source, parts.path))
        
    # VERIFICAÇÃO DE REDE: Executa apenas se a URL passou nas verificações de formato acima
    if not reasons and url:
        if parts.hostname == "github.com" and "/issues/" in parts.path:
            if not is_github_issue_open(url):
                reasons.append("github_issue_closed")
        elif not check_url_alive(url):
            reasons.append("dead_link_404")

    if job.published_at and job.published_at > datetime.now(timezone.utc) + timedelta(days=1):
        reasons.append("published_in_future")

    return reasons


def split_valid_invalid(
    jobs: list[NormalizedJob],
) -> tuple[list[NormalizedJob], list[tuple[NormalizedJob, list[str]]]]:
    """Separa vagas válidas de inválidas, mantendo os motivos de rejeição."""
    valid, invalid = [], []
    for job in jobs:
        reasons = validate_job(job)
        if reasons:
            invalid.append((job, reasons))
        else:
            valid.append(job)
    return valid, invalid