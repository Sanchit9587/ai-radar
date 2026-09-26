# 🤖 AI Radar

Self-hosted daily AI digest pipeline. Every morning at 8 AM it:

1. **Scans your GitHub repos** (all repos you own, auto-discovered) for AI model usage —
   `from_pretrained("...")`, `model="..."`, and known model ids (gpt-*, gemini-*, llama-*, bge-*, whisper, …).
2. **Collects the day's AI news** — newest Hugging Face models, HF Daily Papers, arXiv (cs.AI/CL/LG), and top Hacker News AI stories.
3. **Analyzes** what matters *for you*: flags models you use that got deprecated, and only recommends
   upgrades that are meaningfully better — not merely newer (LLM-powered when a key is configured).
4. **Updates two Google Docs**:
   - *AI Radar — Daily AI News Log* — a new dated section is prepended every day (history preserved).
   - *AI Radar — Project Model Upgrade Tracker* — your full model inventory + recommendations, regenerated when it changes.
5. **Emails you the digest** via Gmail.

```
GitHub API ─┐
HF / arXiv / HN ─┤→ scan+collect → LLM analysis → Google Docs API → Gmail SMTP
                └── state/state.json (repo scan cache, inventory)
```

## Quick start

```bash
git clone https://github.com/Sanchit9587/ai-radar.git
cd ai-radar
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then fill it in (see below)
python main.py --dry-run  # preview the digest without writing/sending anything
python main.py            # real run: update docs + send email
```

## Configuration (.env)

| Variable | What it is | Where to get it |
|---|---|---|
| `GITHUB_TOKEN` | Personal access token | github.com/settings/tokens — `public_repo` scope is enough for public repos (`repo` for private) |
| `GITHUB_USER` | Your GitHub username (optional — auto-detected) | — |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Path to a service-account JSON key | See *Google Docs setup* below |
| `NEWS_DOC_ID` / `TRACKER_DOC_ID` | The two Google Docs IDs (the part after `/d/` in the doc URL) | From the doc URLs |
| `EMAIL_ADDRESS` | Your Gmail address | — |
| `EMAIL_APP_PASSWORD` | Gmail **App Password** (not your normal password) | myaccount.google.com → Security → 2-Step Verification → App passwords |
| `EMAIL_RECIPIENT` | Where the digest goes (defaults to `EMAIL_ADDRESS`) | — |
| `LLM_API_KEY` | Optional but recommended — any OpenAI-compatible key | aistudio.google.com/apikey (free tier works) |
| `LLM_BASE_URL` / `LLM_MODEL` | LLM endpoint; defaults to Gemini's OpenAI-compatible API + `gemini-2.5-flash` | — |

### Google Docs setup (one-time)

1. console.cloud.google.com → create (or pick) a project.
2. *APIs & Services → Library* → enable **Google Docs API**.
3. *APIs & Services → Credentials → Create credentials → Service account* → create it.
4. Open the service account → *Keys → Add key → JSON*. Save the file as `service-account.json`
   in the repo folder (it's gitignored).
5. Copy the service account's email (`xxx@yyy.iam.gserviceaccount.com`) and **share both Google
   Docs with it as Editor** — that's how it gets write access.
6. Put the two doc IDs in `.env`. You can keep using your existing
   *AI Radar — Daily AI News Log* / *Model Upgrade Tracker* docs (just share them) or create fresh ones.

### Gmail setup (one-time)

Your Google account needs 2-Step Verification enabled, then generate an App Password and use it
as `EMAIL_APP_PASSWORD`. Regular passwords won't work with SMTP.

## Scheduling — every day at 8 AM

**Option A — system cron (recommended):**

```cron
CRON_TZ=Asia/Kolkata
0 8 * * * cd /opt/ai-radar && .venv/bin/python main.py >> radar.log 2>&1
```

**Option B — built-in scheduler:**

```bash
nohup python main.py --schedule >> radar.log 2>&1 &
```

`--schedule` sleeps until the next 08:00 local time each day and runs the pipeline.
Set your server's timezone to Asia/Kolkata or export `TZ=Asia/Kolkata`.

## What the code does

| File | Role |
|---|---|
| `main.py` | CLI: `--dry-run`, one-shot (default), `--schedule` |
| `ai_radar/config.py` | Loads `.env`, validates config |
| `ai_radar/github_scanner.py` | Lists your repos, walks git trees, regexes files for model ids; caches per-repo results so unchanged repos aren't re-downloaded |
| `ai_radar/news_sources.py` | HF new models, HF Daily Papers, arXiv, Hacker News — all key-less, all fail-soft |
| `ai_radar/model_matcher.py` | LLM analysis → urgent alerts / meaningful upgrades / news briefs (falls back to a raw digest without a key) |
| `ai_radar/docs_writer.py` | Google Docs API: prepends the daily section, regenerates the tracker, applies heading styles |
| `ai_radar/emailer.py` | Builds and sends the HTML digest via Gmail SMTP |
| `ai_radar/pipeline.py` | Orchestrates everything, keeps `state/state.json` |

## The voice agent (`voice-agent/`)

A Google Apps Script you install into the News Log doc so you can **ask questions out loud about
that day's docs** — mic in, spoken answer out, reads both docs. It's serverless (runs on Chrome's
speech APIs + the Gemini API free tier). See `voice-agent/AI_Radar_Voice_Setup.md`.

## Troubleshooting

| Problem | Fix |
|---|---|
| `Google Docs update failed: 403` | The docs aren't shared with the service account email (Editor role) |
| `email failed: 535` | Wrong app password — regenerate one, 2FA must be enabled |
| `401` from GitHub | Token expired/revoked |
| Everything works but upgrades are empty | `LLM_API_KEY` not set — the no-LLM fallback doesn't judge upgrades |
| Duplicate daily sections | The news-log doc lost its `## ` headings — keep at least one dated `## ` heading in it |

## Notes

- Secrets stay in `.env` / `service-account.json` — both gitignored, never committed.
- The scanner only sees your **default branches** (that's what the GitHub tree API exposes).
- Run `python main.py --dry-run` any time to preview without side effects.
