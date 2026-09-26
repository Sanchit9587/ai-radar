#!/usr/bin/env python3
"""AI Radar — CLI entry point.

Usage:
    python main.py               # run the digest once (use with cron)
    python main.py --dry-run     # print what would be written/sent, change nothing
    python main.py --schedule    # keep running; fires daily at 08:00 local time
"""

import argparse
import time
from datetime import datetime, timedelta


def main():
    ap = argparse.ArgumentParser(description="AI Radar — daily AI digest pipeline")
    ap.add_argument("--dry-run", action="store_true", help="no writes, no email")
    ap.add_argument("--schedule", action="store_true", help="run forever, daily at 08:00 local")
    args = ap.parse_args()

    if args.schedule:
        from ai_radar.pipeline import run

        while True:
            now = datetime.now()
            nxt = now.replace(hour=8, minute=0, second=0, microsecond=0)
            if nxt <= now:
                nxt += timedelta(days=1)
            wait = (nxt - now).total_seconds()
            print(f"[ai-radar] sleeping {wait / 3600:.1f}h until {nxt}")
            time.sleep(wait)
            try:
                run()
            except Exception as e:
                print(f"[ai-radar] run failed: {e}")
    else:
        from ai_radar.config import Config
        from ai_radar.pipeline import run

        problems = Config.validate()
        if problems and not args.dry_run:
            for p in problems:
                print(f"[ai-radar] config problem: {p}")
            raise SystemExit("Fix the config above (see .env.example) or use --dry-run.")

        run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
