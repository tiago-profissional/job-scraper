import re
from urllib.parse import urlsplit
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
    # ATS gringos (Teamtailor, Greenhouse, Lever, etc.)
    "the page you were looking for doesn't exist",
    "this job is no longer available",
    "job is no longer available",
    "position has been filled",
    "job has expired",
    "no longer accepting applications",
    "page not found",
    "404 not found",
    # Plataformas BR (Gupy, etc.)
    "vaga indisponível",
    "vaga encerrada",
    "vaga expirada",
    "processo seletivo encerrado",
    "candidaturas encerradas",
    "página não encontrada",
]

GENERIC_REDIRECT_PATHS = {"", "/", "/jobs", "/vagas", "/careers", "/carreiras"}


def _extract_visible_text(html: str) -> str:
    """Remove scripts/styles e tags HTML para inspecionar apenas o texto visível."""
    cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def check_url_alive(url: str) -> tuple[bool, str]:
    """Verifica se a URL da vaga está ativa e não caiu em soft-404 ou redirect genérico."""
    try:
        response = httpx.get(
            url,
            timeout=8.0,
            headers=DEFAULT_HEADERS,
            follow_redirects=True,
        )

        if response.status_code >= 400:
            return False, f"dead_link_{response.status_code}"

        # Detecta quando uma vaga expirada redireciona para a home ou listagem geral
        original_path = urlsplit(url).path.rstrip("/")
        final_path = urlsplit(str(response.url)).path.rstrip("/")
        if original_path and original_path != final_path and final_path.lower() in GENERIC_REDIRECT_PATHS:
            return False, "soft_404_redirected_to_home"

        raw_html = response.text.lower()
        for indicator in EXPIRED_INDICATORS:
            if indicator in raw_html:
                return False, "soft_404_expired_job"

        visible_text = _extract_visible_text(response.text)
        for indicator in EXPIRED_INDICATORS:
            if indicator in visible_text:
                return False, "soft_404_expired_job"

        # HTML vazio de SPA que falhou ao renderizar conteúdo
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" in content_type and len(visible_text) < 60:
            return False, "soft_404_empty_page"

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