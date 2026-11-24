import json
import re
import time
from urllib.parse import parse_qs, urlsplit

import httpx

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _request_json(
    method: str,
    url: str,
    params: dict[str, str | int | bool] | None = None,
    *,
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
    max_retries: int = 3,
    backoff_factor: float = 1.0,
    timeout: float = 10.0,
) -> dict[str, object] | list[object]:
    if max_retries < 1:
        raise ValueError("max_retries must be at least 1.")

    request = httpx.get if method == "GET" else httpx.post
    for attempt in range(1, max_retries + 1):
        try:
            request_options: dict[str, object] = {"timeout": timeout}
            if params is not None:
                request_options["params"] = params
            if headers is not None:
                request_options["headers"] = headers
            if method == "POST":
                request_options["json"] = payload
            response = request(url, **request_options)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, (dict, list)):
                raise ValueError("Expected a JSON object or array in the API response.")
            return data
        except (httpx.HTTPStatusError, httpx.RequestError) as err:
            status_code = getattr(getattr(err, "response", None), "status_code", None)
            should_retry = isinstance(err, httpx.RequestError) or status_code in RETRYABLE_STATUS_CODES
            if attempt < max_retries and should_retry:
                time.sleep(backoff_factor * (2 ** (attempt - 1)))
                continue
            raise

    raise RuntimeError("HTTP request exhausted retries without returning a response.")


def get_json(
    url: str,
    params: dict[str, str | int | bool] | None = None,
    *,
    headers: dict[str, str] | None = None,
    max_retries: int = 3,
    backoff_factor: float = 1.0,
    timeout: float = 10.0,
) -> dict[str, object]:
    response = _request_json(
        "GET",
        url,
        params=params,
        headers=headers,
        max_retries=max_retries,
        backoff_factor=backoff_factor,
        timeout=timeout,
    )
    if not isinstance(response, dict):
        raise ValueError("Expected a JSON object in the API response.")
    return response


def get_json_list(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    max_retries: int = 3,
    backoff_factor: float = 1.0,
    timeout: float = 10.0,
) -> list[object]:
    response = _request_json(
        "GET",
        url,
        headers=headers,
        max_retries=max_retries,
        backoff_factor=backoff_factor,
        timeout=timeout,
    )
    if not isinstance(response, list):
        raise ValueError("Expected a JSON array in the API response.")
    return response


def post_json(
    url: str,
    payload: dict[str, object],
    *,
    headers: dict[str, str] | None = None,
    max_retries: int = 3,
    backoff_factor: float = 1.0,
    timeout: float = 10.0,
) -> dict[str, object]:
    response = _request_json(
        "POST",
        url,
        payload=payload,
        headers=headers,
        max_retries=max_retries,
        backoff_factor=backoff_factor,
        timeout=timeout,
    )
    if not isinstance(response, dict):
        raise ValueError("Expected a JSON object in the API response.")
    return response


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

EXPIRED_INDICATORS = [
    # Next.js / Vercel / SPAs
    "this page could not be found",
    "next_not_found",
    '"notfound":true',
    '"page":"/404"',
    # ATS internacionais (Teamtailor, Greenhouse, Lever, Workable, etc.)
    "the page you were looking for doesn't exist",
    "this job is no longer available",
    "job is no longer available",
    "position has been filled",
    "job has expired",
    "no longer accepting applications",
    "sorry, this job is closed",
    "page not found",
    "404 not found",
    # Plataformas BR (Gupy, Solides, Kenoby, etc.)
    "vaga indisponível",
    "vaga encerrada",
    "vaga expirada",
    "processo seletivo encerrado",
    "candidaturas encerradas",
    "página não encontrada",
    "esta vaga não está mais disponível",
]

TITLE_ERROR_INDICATORS = (
    "404",
    "not found",
    "não encontrada",
    "vaga encerrada",
    "vaga indisponível",
    "expired",
)

GENERIC_REDIRECT_PATHS = {
    "",
    "/",
    "/jobs",
    "/vagas",
    "/careers",
    "/carreiras",
    "/search",
    "/busca",
    "/empregos",
    "/ofertas",
}

SEARCH_QUERY_KEYS = {"q", "query", "search", "keyword", "keywords", "busca"}

JOB_INTENT_SIGNALS = (
    "we're hiring",
    "we are hiring",
    "now hiring",
    "hiring for",
    "hiring:",
    "job opening for",
    "job opening:",
    "open position for",
    "open position:",
    "open role for",
    "open role:",
    "vacancy announcement",
    "vacancies available",
    "we're looking to hire",
    "we are looking to hire",
    "we're looking for a",
    "we're looking for an",
    "we are looking for a",
    "we are looking for an",
    "join our team as",
    "vaga:",
    "vaga -",
    "vaga para",
    "vaga de",
    "vaga aberta",
    "oportunidade de emprego para",
    "estamos contratando",
    "contratando para",
    "buscamos profissional",
    "buscamos um",
    "buscamos uma",
    "estamos buscando um",
    "estamos buscando uma",
)

JOB_DETAIL_SIGNAL_GROUPS = (
    (
        "requirements",
        "qualifications",
        "required skills",
        "requisitos",
        "qualificações",
        "experiência necessária",
    ),
    (
        "responsibilities",
        "what you'll do",
        "what you will do",
        "duties",
        "responsabilidades",
        "atribuições",
    ),
    (
        "salary",
        "compensation",
        "benefits",
        "full-time",
        "full time",
        "contract",
        "salário",
        "remuneração",
        "benefícios",
        "tempo integral",
    ),
    (
        "location",
        "remote",
        "hybrid",
        "on-site",
        "onsite",
        "localidade",
        "remoto",
        "híbrido",
        "presencial",
    ),
    (
        "how to apply",
        "apply at",
        "apply here",
        "application instructions",
        "candidatar-se",
        "como se candidatar",
        "inscreva-se",
    ),
)

ADZUNA_DETAIL_PATTERN = re.compile(r"^/details/\d+/?$")


def _extract_visible_text(html: str) -> str:
    """Remove scripts/styles e tags HTML para inspecionar apenas o texto visível."""
    cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def _extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.DOTALL | re.IGNORECASE)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip().lower()


def _job_detail_signal_count(text: str) -> int:
    return sum(
        any(signal in text for signal in group)
        for group in JOB_DETAIL_SIGNAL_GROUPS
    )


def _has_job_posting_signals(
    title: str,
    body: str,
    *,
    require_job_intent: bool = False,
) -> bool:
    title_and_body = f"{title} {body}".lower()
    body = body.lower()
    has_job_intent = any(signal in title_and_body for signal in JOB_INTENT_SIGNALS)
    detail_count = _job_detail_signal_count(body)

    if require_job_intent:
        return has_job_intent and detail_count >= 2
    return (has_job_intent and detail_count >= 2) or detail_count >= 3


def _contains_job_posting_schema(value: object) -> bool:
    if isinstance(value, dict):
        schema_type = value.get("@type")
        types = schema_type if isinstance(schema_type, list) else [schema_type]
        if any(
            isinstance(item, str)
            and item.rstrip("/").rsplit("/", 1)[-1].lower() == "jobposting"
            for item in types
        ):
            return True
        return any(_contains_job_posting_schema(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_job_posting_schema(item) for item in value)
    return False


def _has_job_posting_schema(html: str) -> bool:
    if re.search(
        r"""itemtype\s*=\s*["'][^"']*schema\.org/JobPosting["']""",
        html,
        flags=re.IGNORECASE,
    ):
        return True

    scripts = re.findall(
        r"""<script\b[^>]*type\s*=\s*(?:"application/ld\+json"|'application/ld\+json')[^>]*>(.*?)</script>""",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    for script in scripts:
        try:
            data = json.loads(script)
        except json.JSONDecodeError:
            continue
        if _contains_job_posting_schema(data):
            return True
    return False


def _check_redirect_target(original_url: str, final_url: str, source: str | None) -> str | None:
    """Detecta redirects de vaga expirada para home, busca ou listagem genérica."""
    orig = urlsplit(original_url)
    final = urlsplit(final_url)

    orig_path = orig.path.rstrip("/")
    final_path = final.path.rstrip("/")

    if orig_path == final_path and orig.query == final.query:
        return None

    # Caiu na raiz ou em rota genérica de listagem (/jobs, /vagas, /careers, /search)
    if final_path.lower() in GENERIC_REDIRECT_PATHS:
        return "soft_404_redirected_to_listing"

    # Adzuna redirecionou /details/<id> para página de busca/categoria dentro do próprio Adzuna
    if source == "adzuna" and final.hostname and final.hostname.endswith("adzuna.com.br"):
        if not ADZUNA_DETAIL_PATTERN.match(final.path):
            return "soft_404_adzuna_redirect"

    # Redirect adicionou parâmetros típicos de busca (?q=, ?keyword=, ?busca=)
    orig_params = set(parse_qs(orig.query).keys())
    final_params = set(parse_qs(final.query).keys())
    added_params = {k.lower() for k in (final_params - orig_params)}
    if added_params & SEARCH_QUERY_KEYS:
        return "soft_404_redirected_to_search"

    return None


def check_url_alive(
    url: str,
    source: str | None = None,
    *,
    require_job_posting: bool = True,
) -> tuple[bool, str]:
    """Verifica disponibilidade/soft 404 e, opcionalmente, sinais de uma página de vaga."""
    try:
        response = httpx.get(
            url,
            timeout=8.0,
            headers=DEFAULT_HEADERS,
            follow_redirects=True,
        )

        if response.status_code >= 400:
            return False, f"dead_link_{response.status_code}"

        redirect_error = _check_redirect_target(url, str(response.url), source)
        if redirect_error:
            return False, redirect_error

        raw_html = response.text.lower()
        for indicator in EXPIRED_INDICATORS:
            if indicator in raw_html:
                return False, "soft_404_expired_job"

        page_title = _extract_title(response.text)
        if any(err in page_title for err in TITLE_ERROR_INDICATORS):
            return False, "soft_404_title_error"

        visible_text = _extract_visible_text(response.text)
        for indicator in EXPIRED_INDICATORS:
            if indicator in visible_text:
                return False, "soft_404_expired_job"

        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" in content_type and require_job_posting:
            has_job_schema = _has_job_posting_schema(response.text)

            # Casca SPA vazia (Next.js/React que não renderizou conteúdo)
            if not has_job_schema and len(visible_text) < 250:
                return False, "soft_404_thin_or_empty_page"

            if not has_job_schema and not _has_job_posting_signals(page_title, visible_text):
                return False, "soft_404_no_job_signals"

        return True, ""

    except httpx.TimeoutException:
        return False, "dead_link_timeout"
    except httpx.RequestError:
        return False, "dead_link_connection_error"


def _fetch_github_issue(url: str) -> tuple[dict | None, str]:
    parts = urlsplit(url)
    match = re.fullmatch(r"/([^/]+)/([^/]+)/issues/(\d+)/?", parts.path)
    if parts.scheme != "https" or parts.hostname != "github.com" or not match:
        return None, "github_issue_not_valid_job"

    owner, repo, issue_number = match.groups()
    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"

    try:
        response = httpx.get(api_url, timeout=5.0, headers=DEFAULT_HEADERS)
    except httpx.RequestError:
        return None, "github_issue_check_failed"

    if response.status_code == 404:
        return None, "github_issue_not_valid_job"
    if response.status_code != 200:
        return None, "github_issue_check_failed"

    try:
        issue = response.json()
    except json.JSONDecodeError:
        return None, "github_issue_check_failed"
    if not isinstance(issue, dict):
        return None, "github_issue_check_failed"
    return issue, ""


def check_github_issue_job_posting(url: str) -> tuple[bool, str]:
    """Distinguishes invalid GitHub issues from temporary API failures."""
    issue, error = _fetch_github_issue(url)
    if error:
        return False, error
    if issue is None or issue.get("state") != "open" or "pull_request" in issue:
        return False, "github_issue_not_valid_job"

    title = issue.get("title")
    body = issue.get("body")
    if not isinstance(title, str) or not isinstance(body, str):
        return False, "github_issue_not_valid_job"
    if not _has_job_posting_signals(title, body, require_job_intent=True):
        return False, "github_issue_not_valid_job"
    return True, ""


def is_github_issue_open(url: str) -> bool:
    """Consulta a API do GitHub e rejeita issues fechadas e pull requests."""
    issue, error = _fetch_github_issue(url)
    return bool(
        not error
        and issue
        and issue.get("state") == "open"
        and "pull_request" not in issue
    )


def is_github_issue_job_posting(url: str) -> bool:
    """Confirma que a issue está aberta, não é PR e contém sinais de vaga."""
    valid, _ = check_github_issue_job_posting(url)
    return valid
