from scraper.models.job import NormalizedJob
from scraper.normalization.job_normalizer import normalize_job
from scraper.sources.adzuna import AdzunaAdapter
from scraper.sources.arbeitnow import ArbeitnowAdapter
from scraper.sources.remotive import RemotiveAdapter
from scraper.storage.json_store import (
    PROCESSED_JOBS_PATH,
    RAW_JOBS_PATH,
    StorageError,
    persist_jobs,
    persist_raw,
    utc_now,
)
from scraper.storage.mysql_store import cleanup_dead_jobs, persist_jobs_to_mysql
from scraper.validation.job_validator import validate_job


def main() -> None:
    adapters = [
        AdzunaAdapter(),
        RemotiveAdapter(),
        ArbeitnowAdapter(),
    ]

    total_valid_jobs: list[NormalizedJob] = []
    now = utc_now()

    for adapter in adapters:
        print(f"\n--- Running adapter: {adapter.source_slug} ---")
        items = adapter.discover()
        print(f"Jobs found in {adapter.source_slug}: {len(items)}")

        valid_jobs: list[NormalizedJob] = []
        valid_raw_items: list[dict] = []

        for item in items:
            raw_job = adapter.parse(adapter.fetch(item))
            normalized = normalize_job(raw_job)
            reasons = validate_job(normalized)

            if not reasons:
                valid_jobs.append(normalized)
                valid_raw_items.append(item)
            else:
                print(f"Invalid job '{normalized.title}' rejected: {', '.join(reasons)}")

        print(f"Valid: {len(valid_jobs)} | Invalid in source: {len(items) - len(valid_jobs)}")
        total_valid_jobs.extend(valid_jobs)

        try:
            raw_res = persist_raw(
                RAW_JOBS_PATH,
                adapter.source_slug,
                valid_raw_items,
                seen_at=now,
            )
            print(f"raw ({adapter.source_slug}): added {raw_res['added']} / unchanged {raw_res['unchanged']}")
        except StorageError as err:
            print(f"Storage error (raw): {err}")

    try:
        proc_res = persist_jobs(
            PROCESSED_JOBS_PATH,
            total_valid_jobs,
            NormalizedJob,
            seen_at=now,
        )
        print(f"\n--- Total Processed Storage Summary ---")
        print(f"processed: added {proc_res['added']} / unchanged {proc_res['unchanged']}")
    except StorageError as err:
        print(f"Storage error (processed): {err}")

    # Sincroniza vagas válidas e remove vagas expiradas do MySQL
    persist_jobs_to_mysql(total_valid_jobs)
    cleanup_dead_jobs()


if __name__ == "__main__":
    main()