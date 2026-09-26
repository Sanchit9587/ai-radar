"""Google Docs output: prepends the daily news section and rewrites the tracker.

Authenticates with a service account. IMPORTANT: both Google Docs must be
shared with the service account's email (Editor role).

The news log keeps its history: each run inserts the new dated section right
after the intro / above the previous newest section. The tracker is fully
regenerated from the current inventory whenever it changes.
"""

import re

from google.oauth2 import service_account
from googleapiclient.discovery import build

from .config import Config

SCOPES = ["https://www.googleapis.com/auth/documents"]


def get_service():
    creds = service_account.Credentials.from_service_account_file(
        Config.GOOGLE_SA_FILE, scopes=SCOPES
    )
    return build("docs", "v1", credentials=creds)


# --- helpers ---------------------------------------------------------------------


def _para_text(p: dict) -> str:
    return "".join(e.get("textRun", {}).get("content", "") for e in p.get("elements", []))


def get_text(svc, doc_id: str) -> str:
    doc = svc.documents().get(documentId=doc_id).execute()
    lines = []
    for el in doc["body"]["content"]:
        if "paragraph" in el:
            lines.append(_para_text(el["paragraph"]))
        elif "table" in el:
            for row in el["table"]["tableRows"]:
                cells = []
                for cell in row["tableCells"]:
                    cell_text = ""
                    for p in cell.get("content", []):
                        if "paragraph" in p:
                            cell_text += _para_text(p["paragraph"])
                    cells.append(cell_text.strip())
                lines.append(" | ".join(cells))
    return "\n".join(lines)


def _style_headings(svc, doc_id: str):
    """Apply HEADING_* styles to lines starting with #/##/###."""
    doc = svc.documents().get(documentId=doc_id).execute()
    reqs = []
    for el in doc["body"]["content"]:
        p = el.get("paragraph")
        if not p:
            continue
        t = _para_text(p)
        style = None
        if t.startswith("### "):
            style = "HEADING_3"
        elif t.startswith("## "):
            style = "HEADING_2"
        elif t.startswith("# "):
            style = "HEADING_1"
        if style:
            reqs.append(
                {
                    "updateParagraphStyle": {
                        "range": {"startIndex": el["startIndex"], "endIndex": el["endIndex"]},
                        "paragraphStyle": {"namedStyleType": style},
                    }
                }
            )
    if reqs:
        svc.documents().batchUpdate(documentId=doc_id, body={"requests": reqs}).execute()


def _md_to_plain(md: str) -> str:
    """Markdown -> doc-friendly plain text (table separator rows dropped)."""
    out = []
    for line in md.splitlines():
        if re.match(r"^\|[\s:|-]+\|$", line):  # |---|---| separator row
            continue
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1 (\2)", line)
        out.append(line)
    return "\n".join(out)


# --- public API ------------------------------------------------------------------


def prepend_news_section(svc, doc_id: str, heading: str, body_markdown: str):
    """Insert a new dated section above the previous newest one (or at the end)."""
    doc = svc.documents().get(documentId=doc_id).execute()
    body = doc["body"]["content"]

    insert_at = None
    for el in body:
        p = el.get("paragraph")
        if p and _para_text(p).startswith("## "):
            insert_at = el["startIndex"]
            break
    if insert_at is None:
        insert_at = body[-1]["endIndex"] - 1  # very end, before trailing newline

    text = heading + "\n" + _md_to_plain(body_markdown).strip() + "\n\n"
    svc.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{"insertText": {"location": {"index": insert_at}, "text": text}}]},
    ).execute()
    _style_headings(svc, doc_id)


def replace_tracker(svc, doc_id: str, markdown: str):
    """Rewrite everything below the doc title with the given markdown-ish text."""
    doc = svc.documents().get(documentId=doc_id).execute()
    body = doc["body"]["content"]

    # Keep the first element (title); delete the rest, keep the final newline.
    delete_start = body[0]["endIndex"] - 1
    delete_end = body[-1]["endIndex"] - 1
    ops = []
    if delete_end > delete_start:
        ops.append(
            {"deleteContentRange": {"range": {"startIndex": delete_start, "endIndex": delete_end}}}
        )
    text = _md_to_plain(markdown).strip()
    if text:
        text += "\n"
        ops.append({"insertText": {"location": {"index": delete_start}, "text": text}})
    if ops:
        svc.documents().batchUpdate(documentId=doc_id, body={"requests": ops}).execute()
    _style_headings(svc, doc_id)
