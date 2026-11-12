import re
from urllib.parse import parse_qs, urlsplit
import httpx

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

ACTIVE_JOB_SIGNALS = (
    "candidatar",
    "apply",
    "requisitos",
    "requirements",
    "responsabilidades",
    "responsibilities",
    "descrição da vaga",
    "job description",
    "qualificações",
    "qualifications",
    "benefícios",
    "benefits",
    "salário",
    "salary",
    "sobre a vaga",
    "about the job",
    "about the role",
    "what you'll do",
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


def check_url_alive(url: str, source: str | None = None) -> tuple[bool, str]:
    """Verifica se a URL está ativa, não caiu em redirect genérico e contém uma vaga real."""
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
        if "text/html" in content_type:
            has_job_schema = '"jobposting"' in raw_html or "'jobposting'" in raw_html

            # Casca SPA vazia (Next.js/React que não renderizou conteúdo)
            if not has_job_schema and len(visible_text) < 250:
                return False, "soft_404_thin_or_empty_page"

            # Validação positiva: precisa ter schema JobPosting ou termos reais de vaga/candidatura
            if not has_job_schema and not any(sig in visible_text for sig in ACTIVE_JOB_SIGNALS):
                return False, "soft_404_no_job_signals"

        return True, ""

    except httpx.TimeoutException:
        return False, "dead_link_timeout"
    except httpx.RequestError:
        return False, "dead_link_connection_error"


def is_github_issue_open(url: str) -> bool:
    """Consulta a API do GitHub para verificar se a vaga (issue) ainda está aberta."""
    match = re.match(r"https://github\.com/([^/]+)/([^/]+)/issues/(\d+)", url)
    if not match:
        return True

    owner, repo, issue_number = match.groups()
    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"

    try:
        response = httpx.get(api_url, timeout=5.0, headers=DEFAULT_HEADERS)
        if response.status_code == 200:
            return response.json().get("state") == "open"
        return False
    except httpx.RequestError:
        return False