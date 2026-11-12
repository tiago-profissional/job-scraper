import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from scraper.models.job import NormalizedJob
from scraper.fetching.http_client import check_url_alive, is_github_issue_open

ALLOWED_DOMAINS = {
    "adzuna": ("adzuna.com.br",),
    "remotive": ("remotive.com",),
    "arbeitnow": ("*",),
}

JOB_PATH_PATTERNS = {
    "adzuna": re.compile(r"^/details/\d+/?$"),
}

MIN_DESCRIPTION_LENGTH = 50

BLOCKED_PATH_SEGMENTS = {
    "login_page": {"login", "signin", "entrar"},
    "search_page": {"search", "busca"},
}

GENERIC_TITLES = {"vagas", "jobs", "resultados", "search results"}

IGNORED_DESCRIPTION_HOSTS = {
    "chat.whatsapp.com",
    "wa.me",
    "t.me",
    "telegram.me",
    "linkedin.com",
    "www.linkedin.com",
    "github.com",
    "instagram.com",
    "youtube.com",
}


def _domain_allowed(host: str, allowed: tuple[str, ...]) -> bool:
    if "*" in allowed:
        return True
    return any(host == d or host.endswith("." + d) for d in allowed)


def _check_page_type(source: str, path: str) -> list[str]:
    """Rejects login pages, search pages, and others that do not represent a single job."""
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


def _extract_apply_url_from_description(description: str) -> str | None:
    """Extrai o primeiro link externo de candidatura da descrição, ignorando redes sociais."""
    urls = re.findall(r"https?://[^\s<>\"')]+", description)
    for raw_url in urls:
        clean_url = raw_url.rstrip(".,;:!?")
        parsed = urlsplit(clean_url)
        host = (parsed.hostname or "").lower()
        if host and host not in IGNORED_DESCRIPTION_HOSTS and "/referral" not in parsed.path.lower():
            return clean_url
    return None


def validate_job(job: NormalizedJob) -> list[str]:
    """Returns rejection reasons for a job. An empty list indicates a valid job."""
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

    # Validação de rede (source_url + apply_url)
    if not reasons and url:
        is_github_issue = parts.hostname == "github.com" and "/issues/" in parts.path
        if is_github_issue:
            if not is_github_issue_open(url):
                reasons.append("github_issue_closed")
        else:
            is_alive, error_reason = check_url_alive(url)
            if not is_alive:
                reasons.append(error_reason)

        # Valida também o link direto de candidatura (apply_url ou link extraído da issue)
        target_apply_url = str(job.apply_url) if job.apply_url else None
        if not target_apply_url and is_github_issue and job.description:
            target_apply_url = _extract_apply_url_from_description(job.description)

        if not reasons and target_apply_url and target_apply_url != url:
            apply_alive, apply_error = check_url_alive(target_apply_url)
            if not apply_alive:
                reasons.append(f"apply_{apply_error}")

    if job.published_at and job.published_at > datetime.now(timezone.utc) + timedelta(days=1):
        reasons.append("published_in_future")

    return reasons


def split_valid_invalid(
    jobs: list[NormalizedJob],
) -> tuple[list[NormalizedJob], list[tuple[NormalizedJob, list[str]]]]:
    """Separates valid from invalid jobs, preserving the specific rejection reasons."""
    valid, invalid = [], []
    for job in jobs:
        reasons = validate_job(job)
        if reasons:
            invalid.append((job, reasons))
        else:
            valid.append(job)
    return valid, invalid