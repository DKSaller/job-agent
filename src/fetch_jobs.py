import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv

from src.config import load_config

load_dotenv()

BASE_URL = "https://api.adzuna.com/v1/api/jobs/us/search/1"
MILES_TO_KM = 1.609


def _search_adzuna(what, where=None, distance_km=None, max_days=7, remote_only=False):
    """Run one Adzuna search and return the raw list of results."""
    params = {
        "app_id": os.getenv("ADZUNA_APP_ID"),
        "app_key": os.getenv("ADZUNA_APP_KEY"),
        "results_per_page": 50,
        "what": what,
        "max_days_old": max_days,
        "sort_by": "date",
        "content-type": "application/json",
    }
    if where:
        params["where"] = where
    if distance_km:
        params["distance"] = int(distance_km)
    if remote_only:
        params["what_and"] = "remote"

    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("results", [])


def _normalize(raw_job, source="adzuna"):
    """Convert one Adzuna result into our standard job format."""
    return {
        "job_id": f"{source}-{raw_job.get('id')}",
        "title": raw_job.get("title", ""),
        "company": (raw_job.get("company") or {}).get("display_name", ""),
        "location": (raw_job.get("location") or {}).get("display_name", ""),
        "description": raw_job.get("description", ""),
        "url": raw_job.get("redirect_url", ""),
        "date_posted": raw_job.get("created", ""),
        "salary_min": raw_job.get("salary_min"),
        "salary_max": raw_job.get("salary_max"),
        "source": source,
    }


def fetch_jobs(cfg):
    """Fetch jobs for every configured title, local and remote, as a DataFrame."""
    search = cfg["search"]
    loc = cfg["location"]
    titles = search["primary_titles"] + search["adjacent_titles"]
    max_days = search["max_posting_age_days"]
    distance_km = loc["commute_radius_miles"] * MILES_TO_KM

    rows = []
    for title in titles:
        # Local search around home city
        try:
            for r in _search_adzuna(title, loc["home_city"], distance_km, max_days):
                rows.append(_normalize(r))
        except requests.RequestException as e:
            print(f"Local search failed for '{title}': {e}")
        time.sleep(1)

        # Remote search
        if loc["allow_remote"]:
            try:
                for r in _search_adzuna(title, max_days=max_days, remote_only=True):
                    rows.append(_normalize(r))
            except requests.RequestException as e:
                print(f"Remote search failed for '{title}': {e}")
            time.sleep(1)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.drop_duplicates(subset="job_id").reset_index(drop=True)


def apply_basic_filters(df, cfg):
    """Cheap filters (no LLM): excluded title words and salary floor."""
    if df.empty:
        return df

    # Drop titles containing excluded keywords
    for word in cfg["search"]["exclude_title_keywords"]:
        df = df[~df["title"].str.contains(rf"\b{word}\b", case=False, regex=True)]

    # Salary floor: keep jobs with no salary info if config says "include"
    floor = cfg["compensation"]["min_salary"]
    has_salary = df["salary_max"].notna()
    meets_floor = df["salary_max"] >= floor
    if cfg["compensation"]["if_salary_missing"] == "include":
        df = df[~has_salary | meets_floor]
    else:
        df = df[has_salary & meets_floor]

    return df.reset_index(drop=True)


if __name__ == "__main__":
    cfg = load_config()
    raw = fetch_jobs(cfg)
    print(f"Fetched {len(raw)} unique jobs.")
    filtered = apply_basic_filters(raw, cfg)
    print(f"{len(filtered)} remain after basic filters.\n")
    print(filtered[["title", "company", "location", "salary_min"]].head(15).to_string())