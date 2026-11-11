from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class WorkMode(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"


class Seniority(str, Enum):
    INTERN = "intern"
    JUNIOR = "junior"
    MID_LEVEL = "mid_level"
    SENIOR = "senior"


class EmploymentType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"


class RawJob(BaseModel):
    model_config = ConfigDict(extra="forbid")  # unknown fields raise instead of being ignored

    source: str
    source_url: HttpUrl
    external_id: str | None = None
    title: str = Field(min_length=1)  # empty title is an error, as Step 2 requires
    company: str                      # may be "" here; Step 9's validator rejects it
    description: str
    location: str | None = None
    location_area: list[str] = Field(default_factory=list)  # e.g. [país, região, estado, cidade, bairro?]
    work_mode: str | None = None
    seniority: str | None = None
    employment_type: str | None = None
    technologies: list[str] = Field(default_factory=list)
    published_at: str | None = None   # raw value, exactly as the source gave it
    fetched_at: str


class NormalizedJob(RawJob):
    company: str | None = None        # empty company becomes None after normalization
    apply_url: str | None = None      # Direct ATS application link (Gupy, Lever, etc.)
    work_mode: WorkMode | None = None
    seniority: Seniority | None = None
    employment_type: EmploymentType | None = None
    published_at: datetime | None = None
    fetched_at: datetime
    city: str | None = None
    state: str | None = None
    canonical_url: str | None = None
    content_hash: str | None = None
    raw: dict | None = None           # original RawJob, kept for audit
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None