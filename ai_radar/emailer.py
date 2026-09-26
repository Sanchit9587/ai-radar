"""Sends the daily digest email via Gmail SMTP (app password)."""

import html
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .config import Config


def _section_rows(rows, cols):
    tr = "".join(
        "<tr>" + "".join(f"<td style='padding:5px 8px;border-top:1px solid #ddd'>{html.escape(str(c))}</td>" for c in r) + "</tr>"
        for r in rows
    )
    head = "".join(f"<th style='text-align:left;padding:5px 8px'>{h}</th>" for h in cols)
    return (
        f"<table style='border-collapse:collapse;font-size:13px'>"
        f"<tr style='background:#f1f3f4'>{head}</tr>{tr}</table>"
    )


def build_html(analysis: dict, doc_links: dict, run_date: date) -> str:
    parts = []
    parts.append(
        "<html><body style='font-family:Arial,sans-serif;max-width:640px;margin:0 auto;color:#222'>"
        f"<h2 style='color:#1a73e8;margin-bottom:4px'>AI Radar — Daily Digest</h2>"
        f"<p style='color:#666;margin-top:0;font-size:13px'>{run_date.strftime('%A, %d %B %Y')}</p>"
    )

    if analysis.get("urgent"):
        parts.append(
            "<div style='background:#fce8e6;border-left:4px solid #d93025;padding:12px 16px;"
            "border-radius:6px;margin:16px 0'><b>🔴 Urgent</b><ul style='font-size:13px'>"
        )
        for u in analysis["urgent"]:
            parts.append(
                f"<li><b>{html.escape(str(u.get('current', '')))}</b> ({html.escape(str(u.get('project', '')))}): "
                f"{html.escape(str(u.get('issue', '')))} — <i>Fix: {html.escape(str(u.get('fix', '')))}</i></li>"
            )
        parts.append("</ul></div>")

    if analysis.get("upgrades"):
        parts.append("<h3 style='color:#1a73e8'>⚡ Upgrades for your code</h3>")
        parts.append(
            _section_rows(
                [[u.get("project"), u.get("current"), u.get("suggested"), u.get("why")] for u in analysis["upgrades"]],
                ["Project", "Current", "Upgrade to", "Why"],
            )
        )

    if analysis.get("news_briefs"):
        parts.append("<h3 style='color:#1a73e8'>📰 Today in AI</h3><ul style='font-size:13px;line-height:1.5'>")
        for n in analysis["news_briefs"]:
            parts.append(f"<li><b>{html.escape(str(n.get('title', '')))}</b> — {html.escape(str(n.get('why_it_matters', '')))}</li>")
        parts.append("</ul>")

    if analysis.get("trends_brief"):
        parts.append(
            f"<h3 style='color:#1a73e8'>🔥 Trending</h3><p style='font-size:13px'>{html.escape(analysis['trends_brief'])}</p>"
        )

    links = " · ".join(f"<a href='{url}'>{name}</a>" for name, url in doc_links.items())
    parts.append(
        "<hr style='border:none;border-top:1px solid #ddd'>"
        f"<p style='font-size:12px;color:#666'>📄 Full details: {links}<br>Sent by your self-hosted AI Radar.</p>"
        "</body></html>"
    )
    return "".join(parts)


def send_digest(analysis: dict, doc_links: dict, run_date: date, subject: str = None) -> None:
    subject = subject or f"🤖 AI Radar — {run_date.strftime('%d %b %Y')}"
    if analysis.get("urgent"):
        subject += f": {analysis['urgent'][0].get('issue', 'urgent alert')[:60]}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = Config.EMAIL_ADDRESS
    msg["To"] = Config.EMAIL_RECIPIENT
    msg.attach(MIMEText(build_html(analysis, doc_links, run_date), "html"))

    with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT) as server:
        server.starttls()
        server.login(Config.EMAIL_ADDRESS, Config.EMAIL_APP_PASSWORD)
        server.send_message(msg)
