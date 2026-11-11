import html
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from scraper.models.job import (
    EmploymentType,
    NormalizedJob,
    RawJob,
    Seniority,
    WorkMode,
)

KNOWN_ATS_DOMAINS = [
    r"gupy\.io",
    r"greenhouse\.io",
    r"lever\.co",
    r"workable\.com",
    r"solides\.jobs",
    r"kenoby\.com",
    r"bamboohr\.com",
    r"gupy\.com\.br",
]

ATS_REGEX = re.compile(
    rf"https?://[^\s\)\>\]\"\'\`]*(?:{'|'.join(KNOWN_ATS_DOMAINS)})[^\s\)\>\]\"\'\`]*",
    re.IGNORECASE
)


def extract_ats_apply_url(description: str | None) -> str | None:
    """Extrai apenas links diretos de plataformas de RH/ATS reconhecidas."""
    if not description:
        return None
    match = ATS_REGEX.search(description)
    if match:
        return match.group(0).rstrip(".,;)")
    return None


def clean_text(value: str | None) -> str:
    """Collapse repeated whitespace and strip the ends."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def clean_title(title: str | None) -> str:
    return clean_text(title or "")


def clean_company(company: str | None) -> str | None:
    cleaned = clean_text(company or "")
    return cleaned or None  # empty string becomes None


BLOCK_TAGS = [
    "p", "div", "section", "article", "ul", "ol",
    "h1", "h2", "h3", "h4", "h5", "h6", "tr", "blockquote",
]


def _normalize_whitespace(text: str) -> str:
    """Tidy spaces but keep line breaks (clean_text would flatten them)."""
    text = text.replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)  # at most one blank line in a row
    return text.strip()


def clean_description(text: str | None) -> str:
    """Remove HTML from a job description and keep its paragraphs."""
    if not text:
        return ""

    # No tags at all: only decode entities and tidy whitespace.
    if "<" not in text:
        return _normalize_whitespace(html.unescape(text))

    # In HTML, newlines in the source are just spaces. Real breaks come from tags.
    text = re.sub(r"\s+", " ", text)
    soup = BeautifulSoup(text, "html.parser")

    for tag in soup(["script", "style"]):
        tag.decompose()

    for br in soup.find_all("br"):
        br.replace_with("\n")

    for li in soup.find_all("li"):
        li.insert_before("\n")

    for block in soup.find_all(BLOCK_TAGS):
        block.insert_after("\n\n")

    return _normalize_whitespace(soup.get_text())


EMPLOYMENT_MAP = {
    "full_time": EmploymentType.FULL_TIME,
    "part_time": EmploymentType.PART_TIME,
    "contract": EmploymentType.CONTRACT,
    "internship": EmploymentType.INTERNSHIP,
}


def normalize_employment_type(value: str | None) -> EmploymentType | None:
    """Normalize employment type to the EmploymentType enum."""
    if not value:
        return None
    return EMPLOYMENT_MAP.get(clean_text(value).lower())


SENIORITY_KEYWORDS = [
    (" estagiário ", Seniority.INTERN),
    (" estagiario ", Seniority.INTERN),
    (" júnior ", Seniority.JUNIOR),
    (" junior ", Seniority.JUNIOR),
    (" pleno ", Seniority.MID_LEVEL),
    (" sênior ", Seniority.SENIOR),
    (" senior ", Seniority.SENIOR),
]


def normalize_seniority(title: str | None) -> Seniority | None:
    """Detect seniority from a job title. Unknown -> None."""
    if not title:
        return None
    text = f" {clean_text(title).lower()} "
    for keyword, level in SENIORITY_KEYWORDS:
        if keyword in text:
            return level
    return None


WORK_MODE_KEYWORDS = [
    ("híbrid", WorkMode.HYBRID),
    ("hibrid", WorkMode.HYBRID),
    ("hybrid", WorkMode.HYBRID),
    ("remot", WorkMode.REMOTE),
    ("home office", WorkMode.REMOTE),
    ("presencial", WorkMode.ONSITE),
    ("on-site", WorkMode.ONSITE),
    ("onsite", WorkMode.ONSITE),
]


def normalize_work_mode(text: str | None) -> WorkMode | None:
    """Detect work mode from a title or description. Unknown -> None."""
    if not text:
        return None
    lowered = clean_text(text).lower()
    for keyword, mode in WORK_MODE_KEYWORDS:
        if keyword in lowered:
            return mode
    return None


def split_location(area: list[str] | None) -> tuple[str | None, str | None]:
    """Adzuna Brasil area: [país, região, estado, cidade, bairro?]. Returns (city, state)."""
    if not area:
        return None, None
    parts = [p.strip() for p in area if p and p.strip()]
    state = parts[2] if len(parts) >= 3 else None
    city = parts[3] if len(parts) >= 4 else None
    return city, state


def normalize_date(value: str | datetime | None) -> datetime | None:
    """ISO string or datetime -> timezone-aware UTC datetime. Invalid -> None."""
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_job(raw: RawJob) -> NormalizedJob:
    cleaned_desc = clean_description(raw.description)
    city, state = split_location(raw.location_area)

    data = raw.model_dump()
    data.update(
        title=clean_title(raw.title),
        company=clean_company(raw.company),
        description=cleaned_desc,
        apply_url=extract_ats_apply_url(raw.description),
        work_mode=normalize_work_mode(f"{raw.title} {raw.description}"),
        seniority=normalize_seniority(raw.title),
        employment_type=normalize_employment_type(raw.employment_type),
        technologies=normalize_technologies(f"{raw.title} {raw.description}"),
        published_at=normalize_date(raw.published_at),
        city=city,
        state=state,
        raw=raw.model_dump(mode="json"),
    )
    return NormalizedJob(**data)


TECH_PATTERNS = {
    "Python": r"python",
    "Java": r"java(?![\s\-]?script)",
    "JavaScript": r"java[\s\-]?script",
    "TypeScript": r"type[\s\-]?script",
    "Node.js": r"node[\s.\-]?js",
    "React": r"react(?:\.?js)?",
    "Angular": r"angular(?:\.?js)?",
    "Vue.js": r"vue(?:\.?js)?",
    "C#": r"c#|c\s?sharp",
    ".NET": r"\.net|asp\.net|dot\s?net",
    "PHP": r"php",
    "SQL": r"sql",
    "PostgreSQL": r"postgres(?:ql)?",
    "MySQL": r"mysql",
    "Django": r"django",
    "FastAPI": r"fast\s?api",
    "Spring": r"spring(?:\s?boot)?",
    "Docker": r"docker",
    "AWS": r"aws",
    "Git": r"git",
    "HTML": r"html5?",
    "CSS": r"css3?",
    "Flutter": r"flutter",
    "Swift": r"swift",
    "Kotlin": r"kotlin",
}

TECH_REGEXES = {
    name: re.compile(rf"(?<!\w)(?:{pattern})(?!\w)", re.IGNORECASE)
    for name, pattern in TECH_PATTERNS.items()
}


def normalize_technologies(text: str | None) -> list[str]:
    """Find known technologies in text. Sorted, no duplicates, [] if none."""
    if not text:
        return []
    return sorted(name for name, regex in TECH_REGEXES.items() if regex.search(text))