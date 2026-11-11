import re
import httpx

def check_url_alive(url: str) -> tuple[bool, str]:
    """Faz um ping na URL e retorna (sucesso, motivo_do_erro)."""
    headers = {
        "User-Agent": "GG-Job-Scraper/1.0"
    }
    try:
        response = httpx.head(url, timeout=5.0, headers=headers, follow_redirects=True)
        
        if response.status_code == 405:
            response = httpx.get(url, timeout=5.0, headers=headers, follow_redirects=True)
            
        if response.status_code >= 400:
            return False, f"dead_link_{response.status_code}"
            
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
        headers = {"User-Agent": "GG-Job-Scraper/1.0"}
        response = httpx.get(api_url, timeout=5.0, headers=headers)
        if response.status_code == 200:
            return response.json().get("state") == "open"
        return False
    except httpx.RequestError:
        return False

def fetch_url(url, output_path):
    headers = {
        "User-Agent": "GG-Job-Scraper/1.0"
    }

    try:
        r = httpx.get(
            url=url,
            timeout=10.0,
            headers=headers
        )

        r.raise_for_status()
        print("Request successful")

        print("Status:", r.status_code)
        print("Content-Type:", r.headers.get("Content-Type"))
        print("Response size:", len(r.content))

        with open(output_path, "wb") as write_file:
            write_file.write(r.content)

        print("Page saved successfully.")

    except httpx.HTTPStatusError as error:
        print("HTTP error:", error)

    except httpx.RequestError as error:
        print("Request error:", error)

    finally:
        print("HTTP request finished.")

if __name__ == "__main__":
    fetch_url(
        "https://www.example.com",
        "data/raw/response.html"
    )