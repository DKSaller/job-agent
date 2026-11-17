import os
import smtplib
from datetime import date
from email.message import EmailMessage
from html import escape

import pandas as pd
from dotenv import load_dotenv

load_dotenv()


def _safe_url(url):
    """Only allow http(s) links, since job data comes from the open internet."""
    url = str(url or "")
    return url if url.startswith(("http://", "https://")) else ""


def _salary_text(row):
    lo, hi = row.get("salary_min"), row.get("salary_max")
    if pd.notna(lo) and pd.notna(hi):
        return f"${lo:,.0f} - ${hi:,.0f}"
    if pd.notna(hi):
        return f"up to ${hi:,.0f}"
    if pd.notna(lo):
        return f"from ${lo:,.0f}"
    return "not listed"


def build_digest(df):
    """Return (subject, plain_text, html) for a DataFrame of scored jobs."""
    subject = f"Job digest {date.today():%b %d}: {len(df)} matches"
    text_parts = [f"{len(df)} jobs matched your resume today.\n"]
    html_parts = [
        f"<h2>{len(df)} job matches</h2>",
        "<p>Ranked by fit score. Scores are an AI estimate, so read the "
        "posting before applying.</p>",
    ]

    for _, r in df.iterrows():
        title, company = str(r["title"]), str(r["company"])
        location = str(r["location"])
        salary = _salary_text(r)
        url = _safe_url(r["url"])
        matches = ", ".join(r["matching_skills"][:4])
        gaps = "; ".join(r["gaps"][:3])

        text_parts.append(
            f"[{r['fit_score']}] {title} - {company}\n"
            f"  Location: {location} | Salary: {salary}\n"
            f"  Why: {r['reason']}\n"
            f"  Matches: {matches}\n"
            f"  Gaps: {gaps}\n"
            f"  Apply: {url}\n"
        )

        link = f'<a href="{escape(url)}">View and apply</a>' if url else "No link"
        html_parts.append(
            f"<div style='margin:16px 0;padding:12px;border:1px solid #ddd;border-radius:6px'>"
            f"<b>[{r['fit_score']}] {escape(title)}</b> &mdash; {escape(company)}<br>"
            f"<small>{escape(location)} | Salary: {escape(salary)}</small><br>"
            f"<p>{escape(str(r['reason']))}</p>"
            f"<small><b>Matches:</b> {escape(matches)}<br>"
            f"<b>Gaps:</b> {escape(gaps)}</small><br>"
            f"{link}</div>"
        )

    return subject, "\n".join(text_parts), "\n".join(html_parts)


def send_digest(subject, text, html):
    """Email the digest to yourself through Gmail."""
    address = os.getenv("EMAIL_ADDRESS")
    password = (os.getenv("EMAIL_APP_PASSWORD") or "").replace(" ", "")
    if not address or not password:
        raise RuntimeError("EMAIL_ADDRESS or EMAIL_APP_PASSWORD missing from .env")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = address
    msg["To"] = address
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
        server.login(address, password)
        server.send_message(msg)


if __name__ == "__main__":
    # Test send: emails whatever is unsent, but does NOT mark anything as sent.
    from src import store
    from src.config import load_config

    cfg = load_config()
    top = store.get_unsent(cfg["digest"]["min_fit_score"], cfg["digest"]["max_jobs"])
    if top.empty:
        print("No unsent jobs above the score threshold.")
    else:
        subject, text, html = build_digest(top)
        send_digest(subject, text, html)
        print(f"Test digest sent with {len(top)} jobs.")