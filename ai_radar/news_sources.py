"""Collects the day's raw AI news from free, key-less sources.

Sources:
- Hugging Face: newest published models (hub API) and Daily Papers (upvoted research)
- arXiv: latest cs.AI + cs.CL submissions
- Hacker News (Algolia API): high-signal AI stories from the last 24h

Every item is {"title", "url", "source", "detail"}. Everything degrades
gracefully: a failing source never breaks the run.
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests

from .config import Config

UA = {"User-Agent": "ai-radar/1.0 (personal digest tool)"}
TIMEOUT = 25


def _safe_get(url: str, **kw):
    r = requests.get(url, timeout=TIMEOUT, headers=UA, **kw)
    r.raise_for_status()
    return r


def fetch_hf_new_models(limit: int = 12) -> list:
    """Newest models published on the Hugging Face Hub (key-less public API)."""
    try:
        data = _safe_get(
            "https://huggingface.co/api/models",
            params={"sort": "createdAt", "direction": -1, "limit": limit * 3},
        ).json()
    except Exception:
        return []
    items = []
    for m in data:
        tag = m.get("pipeline_tag") or "unknown"
        if tag in {"text-generation", "image-text-to-text", "text-to-image", "automatic-speech-recognition",
                   "image-to-video", "feature-extraction", "text-classification"} or m.get("likes", 0) >= 50:
            items.append(
                {
                    "title": f"{m.get('id', '?')} ({tag})",
                    "url": f"https://huggingface.co/{m.get('id')}",
                    "source": "Hugging Face (new models)",
                    "detail": f"published {m.get('createdAt', '?')[:10]}, {m.get('likes', 0)} likes, "
                              f"{m.get('downloads', 0)} downloads",
                }
            )
        if len(items) >= limit:
            break
    return items


def fetch_hf_daily_papers(limit: int = 6) -> list:
    """Hugging Face Daily Papers — community-upvoted AI research."""
    try:
        data = _safe_get("https://huggingface.co/api/daily_papers").json()
    except Exception:
        return []
    items = []
    for p in data[:limit]:
        paper = p.get("paper", {})
        title = paper.get("title", "").strip()
        if not title:
            continue
        items.append(
            {
                "title": title,
                "url": f"https://huggingface.co/papers/{paper.get('id', '')}",
                "source": "HF Daily Papers",
                "detail": f"{p.get('paper', {}).get('upvotes', p.get('publishedAt', ''))} upvotes · "
                          f"{str(paper.get('publishedAt', ''))[:10]}",
            }
        )
    return items


def fetch_arxiv(limit: int = 10) -> list:
    """Latest cs.AI / cs.CL papers from the arXiv API."""
    try:
        r = _safe_get(
            "http://export.arxiv.org/api/query",
            params={
                "search_query": "cat:cs.AI OR cat:cs.CL OR cat:cs.LG",
                "sortBy": "submittedDate",
                "sortOrder": "descending",
                "max_results": limit,
            },
        )
    except Exception:
        return []
    ns = {"a": "http://www.w3.org/2005/Atom"}
    try:
        root = ET.fromstring(r.text)
    except ET.ParseError:
        return []
    items = []
    for entry in root.findall("a:entry", ns):
        title = re.sub(r"\s+", " ", entry.findtext("a:title", "", ns)).strip()
        link = entry.findtext("a:id", "", ns)
        published = entry.findtext("a:published", "", ns)[:10]
        if not title:
            continue
        items.append(
            {
                "title": title,
                "url": link,
                "source": "arXiv",
                "detail": f"submitted {published}",
            }
        )
    return items


def fetch_hackernews(limit: int = 8) -> list:
    """Top AI stories on Hacker News from the last 24 hours (Algolia API)."""
    day_ago = int((datetime.now(timezone.utc) - timedelta(days=1)).timestamp())
    stories = {}
    for query in ('"AI model" release', "LLM release"):
        try:
            data = _safe_get(
                "https://hn.algolia.com/api/v1/search_by_date",
                params={"query": query, "tags": "story", "numericFilters": f"created_at_i>{day_ago}", "hitsPerPage": 30},
            ).json()
        except Exception:
            continue
        for hit in data.get("hits", []):
            oid = hit.get("objectID")
            if oid and oid not in stories:
                stories[oid] = hit
    ranked = sorted(stories.values(), key=lambda h: h.get("points", 0) or 0, reverse=True)
    items = []
    for h in ranked[:limit]:
        title = h.get("title") or ""
        if not title:
            continue
        items.append(
            {
                "title": title,
                "url": h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}",
                "source": "Hacker News",
                "detail": f"{h.get('points', 0)} points, {h.get('num_comments', 0)} comments",
            }
        )
    return items


def collect_news() -> list:
    """Gather all sources into one list (failures are skipped silently)."""
    items = []
    for fn in (fetch_hackernews, fetch_hf_new_models, fetch_hf_daily_papers, fetch_arxiv):
        try:
            items.extend(fn())
        except Exception:
            continue
    return items
