"""Orchestrates one full AI Radar run:

GitHub scan -> news collection -> LLM analysis -> Google Docs update -> email.

State (repo scan cache + last inventory) lives in a JSON file so unchanged
repos are not re-downloaded on every run.
"""

import json
import os
from datetime import date, datetime

from . import docs_writer, emailer, github_scanner, news_sources
from .config import Config
from .model_matcher import analyze


def _load_state() -> dict:
    if os.path.exists(Config.STATE_FILE):
        try:
            with open(Config.STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_state(state: dict):
    os.makedirs(os.path.dirname(Config.STATE_FILE) or ".", exist_ok=True)
    with open(Config.STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def render_news_markdown(analysis: dict, run_date: date) -> str:
    lines = []
    if analysis.get("urgent"):
        lines.append("### Urgent")
        for u in analysis["urgent"]:
            lines.append(f"- **{u.get('current', '')}** ({u.get('project', '')}): {u.get('issue', '')} — fix: {u.get('fix', '')}")
        lines.append("")
    if analysis.get("news_briefs"):
        lines.append("### Top stories")
        for i, n in enumerate(analysis["news_briefs"], 1):
            lines.append(f"{i}. **{n.get('title', '')}** — {n.get('why_it_matters', '')}")
        lines.append("")
    if analysis.get("upgrades"):
        lines.append("### Upgrade opportunities")
        for u in analysis["upgrades"]:
            lines.append(
                f"- **{u.get('project', '')}**: {u.get('current', '')} → {u.get('suggested', '')} ({u.get('why', '')})"
            )
        lines.append("")
    if analysis.get("trends_brief"):
        lines.append("### Trending")
        lines.append(analysis["trends_brief"])
    return "\n".join(lines)


def render_tracker_markdown(inventory: list, analysis: dict, run_date: date) -> str:
    by_repo = {}
    for f in inventory:
        by_repo.setdefault(f["repo"].split("/")[-1], []).append(f)

    lines = [f"Updated: {run_date.strftime('%d %b %Y')} · {len(inventory)} model usages across {len(by_repo)} projects."]

    lines.append("")
    lines.append("## Current model inventory")
    for repo in sorted(by_repo):
        lines.append(f"### {repo}")
        for f in by_repo[repo]:
            lines.append(f"- `{f['model']}` — {f['path']}")
        lines.append("")

    if analysis.get("urgent") or analysis.get("upgrades"):
        lines.append("## Upgrade recommendations")
        for u in analysis.get("urgent", []):
            lines.append(
                f"### URGENT — {u.get('current', '')} ({u.get('project', '')})\n"
                f"{u.get('issue', '')}\n\nFix: {u.get('fix', '')}\n"
            )
        for u in analysis.get("upgrades", []):
            lines.append(
                f"### {u.get('current', '')} → {u.get('suggested', '')} ({u.get('project', '')})\n"
                f"{u.get('why', '')}\n"
            )
    else:
        lines.append("## Upgrade recommendations")
        lines.append("No meaningful upgrades flagged today.")

    lines.append(
        "\n*Method: repos scanned via the GitHub API for `from_pretrained`, "
        "`model=` and known model-id patterns. Judgement by LLM when configured.*"
    )
    return "\n".join(lines)


def run(dry_run: bool = False) -> dict:
    run_date = date.today()
    print(f"[ai-radar] run for {run_date} (dry_run={dry_run})")

    state = _load_state()
    inventory, scan_stats = github_scanner.scan_github(state)
    print(f"[ai-radar] inventory: {len(inventory)} usages "
          f"(repos scanned {scan_stats['scanned']}, cached {scan_stats['skipped_cached']})")

    news_items = news_sources.collect_news()
    print(f"[ai-radar] news items collected: {len(news_items)}")

    analysis = analyze(inventory, news_items)
    print(f"[ai-radar] analysis: {len(analysis.get('urgent', []))} urgent, "
          f"{len(analysis.get('upgrades', []))} upgrades, "
          f"{len(analysis.get('news_briefs', []))} news briefs")

    doc_links = {
        "Daily AI News Log": f"https://docs.google.com/document/d/{Config.NEWS_DOC_ID}/edit",
        "Model Upgrade Tracker": f"https://docs.google.com/document/d/{Config.TRACKER_DOC_ID}/edit",
    }

    inventory_changed = inventory != state.get("last_inventory")
    results = {"docs_updated": False, "email_sent": False, "dry_run": dry_run}

    if dry_run:
        print("[ai-radar] DRY RUN — would write docs and send email:")
        print(render_news_markdown(analysis, run_date))
        return results

    # --- Google Docs ---
    try:
        svc = docs_writer.get_service()
        docs_writer.prepend_news_section(
            svc,
            Config.NEWS_DOC_ID,
            run_date.strftime("%A, %d %B %Y"),
            render_news_markdown(analysis, run_date),
        )
        if inventory_changed:
            docs_writer.replace_tracker(
                svc, Config.TRACKER_DOC_ID, render_tracker_markdown(inventory, analysis, run_date)
            )
        results["docs_updated"] = True
        print("[ai-radar] Google Docs updated")
    except Exception as e:
        print(f"[ai-radar] WARNING: Google Docs update failed: {e}")

    # --- Email ---
    try:
        emailer.send_digest(analysis, doc_links, run_date)
        results["email_sent"] = True
        print(f"[ai-radar] digest emailed to {Config.EMAIL_RECIPIENT}")
    except Exception as e:
        print(f"[ai-radar] WARNING: email failed: {e}")

    state["last_inventory"] = inventory
    state["last_run"] = datetime.now().isoformat()
    _save_state(state)
    print("[ai-radar] done")
    return results
