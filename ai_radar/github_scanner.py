"""Scans your GitHub repos for AI model usage.

Strategy: list repos owned by the user, and for each repo whose default branch
changed since the last run, walk the git tree, download candidate source files
and regex them for model identifiers (from_pretrained(...), model="...",
known vendor-prefixed ids like gpt-*/gemini-*/llama-*/bge-*/...).
"""

import base64
import re
from dataclasses import dataclass, asdict, field

import requests

from .config import Config

GITHUB_API = "https://api.github.com"

SCAN_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".ipynb", ".json",
    ".yaml", ".yml", ".md", ".txt", ".toml", ".cfg", ".env",
}
SKIP_PATH_PARTS = ("node_modules", ".min.js", "package-lock", "package-lock.json", ".git/", "dist/", "build/", "vendor/")


# --- regexes for model identifiers -------------------------------------------------

# Direct API calls: from_pretrained("org/name") / model="gpt-4o-mini"
RE_FROM_PRETRAINED = re.compile(r"from_pretrained\(\s*[\"']([^\"']+)[\"']")
RE_MODEL_ASSIGN = re.compile(r"\bmodel[_\-]?(?:name|id)?\s*[=:]\s*[\"']([^\"']{3,100})[\"']", re.IGNORECASE)
RE_HF_ID = re.compile(r"[\"']([A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]{2,})[\"']")
RE_VENDOR_ID = re.compile(
    r"[\"']((?:gpt|o1|o3|o4|chatgpt|claude|gemini|llama|meta-llama|unsloth|qwen|qwen2|qwen3|"
    r"deepseek|mistral|ministral|mixtral|grok|kimi|phi|gemma|smollm|bge|e5|gte|all-MiniLM|"
    r"sentence-transformers|whisper|parler|sarvam|ai4bharat|distilwhisper|nomic|bark|"
    r"cross-encoder|ms-marco|clip|yolo|detr|stable-diffusion|sdxl|flux)[-_a-zA-Z0-9./]*)[\"']",
    re.IGNORECASE,
)


@dataclass
class Finding:
    repo: str
    path: str
    model: str
    context: str = field(default="")


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "Authorization": f"token {Config.GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "ai-radar",
        }
    )
    return s


def _get(s: requests.Session, url: str, **kw):
    r = s.get(url, timeout=30, **kw)
    r.raise_for_status()
    return r.json()


def detect_login(s: requests.Session) -> str:
    if Config.GITHUB_USER:
        return Config.GITHUB_USER
    return _get(s, f"{GITHUB_API}/user")["login"]


def list_repos(s: requests.Session, login: str) -> list:
    repos = []
    page = 1
    while True:
        batch = _get(
            s,
            f"{GITHUB_API}/user/repos",
            params={
                "affiliation": "owner",
                "per_page": 100,
                "page": page,
                "sort": "pushed",
            },
        )
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return [r for r in repos if not r.get("fork") and r.get("size", 0) > 0]


CONFIG_NAME_RE = re.compile(
    r".*(?:API_KEY|_KEY|_TOKEN|_URL|_SECRET|_ENDPOINT|_HOST|_PORT|_PATH|_DIR|_FILE|_NAME|_ID|_SIZE)$",
    re.IGNORECASE,
)


def _looks_like_config_name(candidate: str) -> bool:
    """Reject env-var/config names like GEMINI_API_KEY that regexes pick up as vendor ids."""
    if CONFIG_NAME_RE.match(candidate):
        return True
    lowered = candidate.lower()
    return any(x in lowered for x in ("api_key", "secret", "password", "_env"))


def scan_file_text(text: str, repo: str, path: str) -> list:
    findings = []
    seen = set()

    def add(model: str, ctx: str):
        model = model.strip()
        if (
            not model
            or model.lower() in seen
            or len(model) < 3
            or model.count(".") > 3
            or model.lower() in {"main", "test", "default", "latest", "model", "base", "true", "false"}
            or _looks_like_config_name(model)
        ):
            return
        seen.add(model.lower())
        findings.append(Finding(repo=repo, path=path, model=model, context=ctx.strip()[:160]))

    for m in RE_FROM_PRETRAINED.finditer(text):
        add(m.group(1), text[max(0, m.start() - 40) : m.end() + 20])
    for m in RE_MODEL_ASSIGN.finditer(text):
        add(m.group(1), text[max(0, m.start() - 40) : m.end() + 20])
    for m in RE_VENDOR_ID.finditer(text):
        add(m.group(1), text[max(0, m.start() - 40) : m.end() + 20])
    for m in RE_HF_ID.finditer(text):
        candidate = m.group(1)
        # Only accept org/name ids that look like HF model ids, not file paths
        if "/" in candidate and not candidate.endswith((".py", ".js", ".ts", ".json", ".md", ".yaml", ".txt", ".png", ".jpg")):
            if RE_VENDOR_ID.fullmatch(candidate) or candidate.split("/")[0] in {
                "openai", "meta-llama", "unsloth", "Qwen", "mistralai", "deepseek-ai",
                "sentence-transformers", "BAAI", "ai4bharat", "google", "microsoft",
                "facebook", "sarvamai", "THUDM", "internlm", "moonshotai", "01-ai",
            }:
                add(candidate, text[max(0, m.start() - 40) : m.end() + 20])
    return findings


def scan_repo(s: requests.Session, repo: dict) -> list:
    full_name = repo["full_name"]
    branch = repo.get("default_branch") or "main"
    try:
        tree = _get(s, f"{GITHUB_API}/repos/{full_name}/git/trees/{branch}", params={"recursive": "1"})
    except requests.RequestException:
        return []
    if tree.get("truncated"):
        pass  # very large repo; we scan what we got

    findings = []
    checked = 0
    for item in tree.get("tree", []):
        if item["type"] != "blob" or checked >= Config.MAX_FILES_PER_REPO:
            continue
        path = item.get("path", "")
        if any(part in path for part in SKIP_PATH_PARTS):
            continue
        if not any(path.endswith(ext) for ext in SCAN_EXTENSIONS):
            continue
        if item.get("size", 0) > Config.MAX_FILE_BYTES:
            continue
        checked += 1
        try:
            blob = _get(s, item["url"])
            content = base64.b64decode(blob["content"]).decode("utf-8", errors="ignore")
        except (requests.RequestException, KeyError, ValueError):
            continue
        findings.extend(scan_file_text(content, full_name, path))
    return findings


def scan_github(state: dict) -> tuple:
    """Scan repos that changed since the last run.

    Returns (inventory, stats). `inventory` is a sorted, deduplicated list of
    findings across ALL repos (old + newly scanned); per-repo findings are
    cached in state so unchanged repos aren't re-downloaded.
    """
    s = _session()
    login = detect_login(s)
    repos = list_repos(s, login)[: Config.MAX_REPOS]

    cache: dict = {r["full_name"]: r for r in state.get("repo_findings", [])}
    stats = {"repos": len(repos), "scanned": 0, "skipped_cached": 0}

    for repo in repos:
        full_name = repo["full_name"]
        pushed = repo.get("pushed_at", "")
        cached = cache.get(full_name)
        if cached and cached.get("pushed_at") == pushed:
            stats["skipped_cached"] += 1
            continue
        findings = scan_repo(s, repo)
        cache[full_name] = {
            "full_name": full_name,
            "pushed_at": pushed,
            "findings": [asdict(f) for f in findings],
        }
        stats["scanned"] += 1

    state["repo_findings"] = list(cache.values())

    inventory = {}
    for entry in cache.values():
        for f in entry.get("findings", []):
            key = (f["repo"], f["path"], f["model"].lower())
            inventory[key] = f
    return sorted(inventory.values(), key=lambda f: (f["repo"], f["model"])), stats
