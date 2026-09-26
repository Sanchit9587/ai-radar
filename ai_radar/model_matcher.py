"""Turns (inventory + raw news) into the daily digest.

If an LLM key is configured, uses it to pick the significant stories and to
judge which of your in-use models have a *meaningfully better* replacement
(not merely newer). Without a key, falls back to a deterministic digest.
"""

import json
import re

import requests

from .config import Config

SYSTEM_PROMPT = """You are the AI Radar analyst. You maintain a daily digest for a developer.

You get: (1) the developer's current AI model inventory (project, file, model id) and
(2) a raw feed of today's AI news items.

Return STRICT JSON only, no markdown fences, with this shape:
{
  "urgent": [{"project": "...", "current": "...", "issue": "...", "fix": "..."}],
  "upgrades": [{"project": "...", "current": "...", "suggested": "...", "why": "..."}],
  "news_briefs": [{"title": "...", "why_it_matters": "..."}],
  "trends_brief": "one short paragraph about what's trending and why it matters"
}

Rules:
- urgent: only models in the inventory that are deprecated/shut down or clearly broken.
- upgrades: only when a newer model is MEANINGFULLY better for that use case
  (benchmarks, price, capability class) — not just newer. Max 5, best first.
- news_briefs: the 4-6 most significant items from the feed, one line of why each matters.
- If nothing qualifies for a section, return an empty list / empty string."""


def _extract_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return None


def llm_analyze(inventory: list, news_items: list) -> dict:
    """Ask the configured OpenAI-compatible LLM for the digest JSON."""
    inventory_brief = [
        {"project": f["repo"].split("/")[-1], "file": f["path"], "model": f["model"]}
        for f in inventory
    ]
    user_payload = {
        "inventory": inventory_brief,
        "news_feed": [
            {"title": n["title"], "source": n["source"], "detail": n["detail"], "url": n["url"]}
            for n in news_items
        ][:60],
    }
    resp = requests.post(
        f"{Config.LLM_BASE_URL.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {Config.LLM_API_KEY}"},
        json={
            "model": Config.LLM_MODEL,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_payload, indent=1)},
            ],
        },
        timeout=120,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    result = _extract_json(content)
    if result is None:
        raise ValueError("LLM did not return parseable JSON")
    result.setdefault("urgent", [])
    result.setdefault("upgrades", [])
    result.setdefault("news_briefs", [])
    result.setdefault("trends_brief", "")
    return result


def fallback_analyze(inventory: list, news_items: list) -> dict:
    """No-LLM digest: raw top items + plain inventory. No upgrade judgement."""
    return {
        "urgent": [],
        "upgrades": [],
        "news_briefs": [
            {"title": f"{n['title']} — {n['detail']}", "why_it_matters": n["source"]}
            for n in news_items[:6]
        ],
        "trends_brief": (
            f"{len(news_items)} items collected. Configure LLM_API_KEY to get "
            "significance filtering and upgrade recommendations."
        ),
    }


def analyze(inventory: list, news_items: list) -> dict:
    if Config.LLM_API_KEY:
        try:
            return llm_analyze(inventory, news_items)
        except Exception as e:  # fall back rather than fail the run
            result = fallback_analyze(inventory, news_items)
            result["trends_brief"] = (
                f"(LLM analysis failed: {e}. Showing unfiltered feed.) " + result["trends_brief"]
            )
            return result
    return fallback_analyze(inventory, news_items)
