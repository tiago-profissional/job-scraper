import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from scraper.models.job import NormalizedJob
import httpx

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


def _is_link_alive(url: str) -> bool:
    """Verifies if the URL returns a valid HTTP status (under 400)."""
    try:
        # A HEAD request is faster than GET as it only fetches headers
        response = httpx.head(url, timeout=5.0, follow_redirects=True)
        return response.status_code < 400
    except httpx.RequestError: 
        return False


def _is_github_issue_open(url: str) -> bool:
    """Queries the GitHub API to check if an issue is not closed."""
    # Matches URLs like: https://github.com/backend-br/vagas/issues/12384
    # Fixed regex with capture groups () for owner and repo
    match = re.match(r"https://github\.com/([^/]+)/([^/]+)/issues/(\d+)", url)
    if not match:
        return True # Bypass if it is a generic GitHub link, not an issue
    
    owner, repo, issue_number = match.groups()
    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
    
    try: 
        response = httpx.get(api_url, timeout=5.0)
        
        if response.status_code == 200:
            return response.json().get("state") == "open"
        return False
    except httpx.RequestError:
        return False


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
        
    # NEW: Active network check to prevent 404s and closed GitHub issues
    if not reasons and url:
        if parts.hostname == "github.com" and "/issues/" in parts.path:
            if not _is_github_issue_open(url):
                reasons.append("github_issue_closed")
        elif not _is_link_alive(url):
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