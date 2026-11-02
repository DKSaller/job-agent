import re
from pathlib import Path

import pdfplumber

RESUME_PDF = Path("data/resume.pdf")
RESUME_TXT = Path("data/resume.txt")


def extract_resume_text(pdf_path=RESUME_PDF):
    """Pull all text out of the resume PDF."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"{pdf_path} not found. Put your resume there first.")

    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")

    text = "\n".join(pages)
    text = re.sub(r"[ \t]+", " ", text)      # collapse repeated spaces
    text = re.sub(r"\n{3,}", "\n\n", text)   # collapse blank-line runs
    return text.strip()


def redact_contact_info(text):
    """Remove emails and phone numbers before the text goes to any API."""
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[email removed]", text)
    text = re.sub(r"(\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", "[phone removed]", text)
    return text


def load_resume_text(refresh=False):
    """Return cleaned resume text, using a cached copy unless refresh=True."""
    if RESUME_TXT.exists() and not refresh:
        return RESUME_TXT.read_text(encoding="utf-8")

    text = redact_contact_info(extract_resume_text())
    RESUME_TXT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    text = load_resume_text(refresh=True)
    print(f"Extracted {len(text)} characters, {len(text.split())} words.\n")
    print(text[:1500])