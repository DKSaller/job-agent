import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

DB_PATH = Path("data/jobs.sqlite")

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    title TEXT,
    company TEXT,
    location TEXT,
    url TEXT,
    date_posted TEXT,
    source TEXT,
    salary_min REAL,
    salary_max REAL,
    fit_score INTEGER,
    apply_recommendation INTEGER,
    matching_skills TEXT,
    gaps TEXT,
    reason TEXT,
    status TEXT DEFAULT 'new',
    first_seen TEXT,
    sent_at TEXT
);
"""


def _connect():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(SCHEMA)
    return conn


def _none_if_nan(value):
    return None if pd.isna(value) else value


def get_seen_ids():
    """Return the set of job_ids already scored and saved."""
    with closing(_connect()) as conn:
        rows = conn.execute("SELECT job_id FROM jobs").fetchall()
    return {r[0] for r in rows}


def filter_unseen(df):
    """Drop jobs that are already in the database."""
    if df.empty:
        return df
    seen = get_seen_ids()
    return df[~df["job_id"].isin(seen)].reset_index(drop=True)


def save_scored(df):
    """Insert scored jobs. Jobs already in the table are left untouched."""
    if df.empty:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    saved = 0
    with closing(_connect()) as conn:
        for _, r in df.iterrows():
            cur = conn.execute(
                """INSERT OR IGNORE INTO jobs
                   (job_id, title, company, location, url, date_posted, source,
                    salary_min, salary_max, fit_score, apply_recommendation,
                    matching_skills, gaps, reason, status, first_seen)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?)""",
                (
                    r["job_id"], r["title"], r["company"], r["location"],
                    r["url"], r["date_posted"], r["source"],
                    _none_if_nan(r["salary_min"]), _none_if_nan(r["salary_max"]),
                    int(r["fit_score"]), int(bool(r["apply_recommendation"])),
                    json.dumps(list(r["matching_skills"])),
                    json.dumps(list(r["gaps"])),
                    r["reason"], now,
                ),
            )
            saved += cur.rowcount
        conn.commit()
    return saved


def get_unsent(min_score, limit):
    """Top recommended jobs that haven't been sent yet, best first."""
    with closing(_connect()) as conn:
        df = pd.read_sql_query(
            """SELECT * FROM jobs
               WHERE status = 'new' AND apply_recommendation = 1 AND fit_score >= ?
               ORDER BY fit_score DESC LIMIT ?""",
            conn,
            params=(min_score, limit),
        )
    for col in ("matching_skills", "gaps"):
        df[col] = df[col].apply(json.loads)
    return df


def set_status(job_ids, status):
    """Update status ('new', 'sent', 'applied', 'rejected') for one or more jobs."""
    if isinstance(job_ids, str):
        job_ids = [job_ids]
    sent_at = datetime.now(timezone.utc).isoformat() if status == "sent" else None
    with closing(_connect()) as conn:
        for job_id in job_ids:
            conn.execute(
                "UPDATE jobs SET status = ?, sent_at = COALESCE(?, sent_at) WHERE job_id = ?",
                (status, sent_at, job_id),
            )
        conn.commit()