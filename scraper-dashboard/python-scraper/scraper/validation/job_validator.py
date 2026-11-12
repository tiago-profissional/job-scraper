import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from scraper.fetching.http_client import check_url_alive, is_github_issue_open
from scraper.models.job import NormalizedJob, WorkMode

ALLOWED_DOMAINS = {
    "adzuna": ("adzuna.com.br",),
    "remotive": ("remotive.com",),
    "arbeitnow": ("*",),
}

JOB_PATH_PATTERNS = {
    "adzuna": re.compile(r"^/details/\d+/?$"),
}

MIN_DESCRIPTION_LENGTH = 80
MAX_JOB_AGE_DAYS = 45

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

# Padrões para barrar vagas em alemão / outros idiomas fora do escopo PT/EN
GERMAN_GENDER_TAG = re.compile(r"\([mwfd]/[mwfd]/[mwfd]\)", re.IGNORECASE)
GERMAN_RECRUITMENT_WORDS = (
    "wir suchen",
    "deine aufgaben",
    "dein profil",
    "kenntnisse",
    "erfahrung",
    "vollzeit",
    "teilzeit",
    "gehalt",
    "bewerbung",
    "unbefristet",
    "standort",
)

REMOTE_HINTS = (
    "remote",
    "remoto",
    "home office",
    "anywhere",
    "worldwide",
    "latam",
    "latin america",
    "américa latina",
    "americas",
)

BRAZIL_HINTS = (
    "brasil",
    "brazil",
    "ceará",
    "ceara",
    "fortaleza",
    "recife",
    "salvador",
    "natal",
    "joão pessoa",
    "maceió",
    "teresina",
    "são luís",
    "aracaju",
    "são paulo",
    "rio de janeiro",
    "belo horizonte",
    "curitiba",
    "porto alegre",
    "florianópolis",
    "brasília",
)

FOREIGN_ONLY_RESTRICTIONS = (
    "us only",
    "usa only",
    "uk only",
    "germany only",
    "nur in deutschland",
    "eu only",
    "europe only",
    "canada only",
)


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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


def _is_unsupported_language(job: NormalizedJob) -> bool:
    """Detecta vagas em alemão (muito comuns no Arbeitnow) ou fora de PT/EN."""
    sample = f"{job.title} {job.description[:1500]}".lower()
    if GERMAN_GENDER_TAG.search(sample):
        return True
    german_hits = sum(1 for word in GERMAN_RECRUITMENT_WORDS if word in sample)
    return german_hits >= 2


def _is_outside_target_scope(job: NormalizedJob) -> bool:
    """Garante que vagas de fontes globais sejam remotas aceitando BR ou dentro do Brasil."""
    if job.source == "adzuna":
        return False

    location_text = f"{job.location or ''} {job.title}".lower()

    if any(restriction in location_text for restriction in FOREIGN_ONLY_RESTRICTIONS):
        return True

    if any(br in location_text for br in BRAZIL_HINTS):
        return False

    is_remote = job.work_mode == WorkMode.REMOTE or any(r in location_text for r in REMOTE_HINTS)
    return not is_remote


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
    elif len(job.description.strip()) < MIN_DESCRIPTION_LENGTH:
        reasons.append("description_too_short")

    # Filtro de idioma e escopo antes de gastar requisição HTTP
    if not reasons:
        if _is_unsupported_language(job):
            reasons.append("unsupported_language")
        elif _is_outside_target_scope(job):
            reasons.append("outside_target_scope")

    # Filtro de validade por data de publicação
    if job.published_at:
        now_utc = datetime.now(timezone.utc)
        pub_utc = _to_utc(job.published_at)
        if pub_utc > now_utc + timedelta(days=1):
            reasons.append("published_in_future")
        elif pub_utc < now_utc - timedelta(days=MAX_JOB_AGE_DAYS):
            reasons.append("job_expired_by_date")

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
            is_alive, error_reason = check_url_alive(url, source=job.source)
            if not is_alive:
                reasons.append(error_reason)

        target_apply_url = str(job.apply_url) if job.apply_url else None
        if not target_apply_url and is_github_issue and job.description:
            target_apply_url = _extract_apply_url_from_description(job.description)

        if not reasons and target_apply_url and target_apply_url != url:
            apply_alive, apply_error = check_url_alive(target_apply_url)
            if not apply_alive:
                reasons.append(f"apply_{apply_error}")

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