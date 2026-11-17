import argparse

from src import store
from src.config import load_config
from src.fetch_jobs import apply_basic_filters, apply_title_filter, fetch_jobs
from src.notify import build_digest, send_digest
from src.resume_parser import load_resume_text
from src.scorer import score_jobs


def run(max_jobs=None, send=True):
    cfg = load_config()
    resume = load_resume_text()

    raw = fetch_jobs(cfg)
    basic = apply_basic_filters(raw, cfg)
    kept, _ = apply_title_filter(basic, cfg)
    new = store.filter_unseen(kept)
    print(f"{len(raw)} fetched, {len(kept)} passed filters, {len(new)} not seen before.")

    scored = score_jobs(new, resume, cfg, max_jobs=max_jobs)
    saved = store.save_scored(scored)
    print(f"Scored and saved {saved} jobs.")

    top = store.get_unsent(cfg["digest"]["min_fit_score"], cfg["digest"]["max_jobs"])
    print(f"{len(top)} jobs ready for the digest.")

    if top.empty:
        print("Nothing to send.")
        return top

    if send:
        subject, text, html = build_digest(top)
        send_digest(subject, text, html)
        store.set_status(top["job_id"].tolist(), "sent")
        print(f"Digest emailed with {len(top)} jobs.")
    else:
        for _, r in top.iterrows():
            print(f"[{r['fit_score']}] {r['title']} @ {r['company']}")
    return top


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-jobs", type=int, default=None,
                        help="cap how many jobs get scored this run")
    parser.add_argument("--no-email", action="store_true",
                        help="print the digest instead of emailing it")
    args = parser.parse_args()
    run(max_jobs=args.max_jobs, send=not args.no_email)