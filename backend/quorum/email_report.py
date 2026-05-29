"""Daily portfolio email — composes and sends a clean HTML report.

Provider: Resend (RESEND_API_KEY) primary; Gmail SMTP (GMAIL_USER/GMAIL_APP_PASSWORD)
fallback. If neither is configured, the report is rendered and returned but not sent
(so the pipeline never crashes and you can preview the HTML).
"""
from __future__ import annotations

import datetime as dt
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
RESEND_FROM = os.getenv("RESEND_FROM", "QUORUM <onboarding@resend.dev>").strip()
GMAIL_USER = os.getenv("GMAIL_USER", "").strip()
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").strip()


def email_enabled() -> bool:
    return bool(RESEND_API_KEY or (GMAIL_USER and GMAIL_APP_PASSWORD))


def _pct(x: float) -> str:
    return f"{x*100:+.1f}%"


def render_report(snapshot: dict, daily: dict | None, alerts: list[str]) -> tuple[str, str]:
    """Return (subject, html). `daily` is the run_daily_step output (may be None)."""
    val = snapshot.get("value", 0)
    ret = snapshot.get("total_return", 0)
    today = dt.date.today().isoformat()
    arrow = "▲" if ret >= 0 else "▼"
    color = "#0E9F6E" if ret >= 0 else "#E02424"

    subject = f"QUORUM · Portfolio ${val:,.0f} ({_pct(ret)}) · {today}"

    holdings_rows = ""
    for h in snapshot.get("holdings", [])[:10]:
        holdings_rows += f"""
        <tr>
          <td style="padding:8px 12px;font-family:monospace;font-weight:600;color:#0A2540">{h['ticker']}</td>
          <td style="padding:8px 12px;color:#425466">{h['name']}</td>
          <td style="padding:8px 12px;color:#697386;font-size:12px">{h['sector']}</td>
          <td style="padding:8px 12px;text-align:right;font-family:monospace">${h['value']:,.0f}</td>
        </tr>"""

    alerts_html = ""
    if alerts:
        items = "".join(f'<li style="margin:4px 0">{a}</li>' for a in alerts)
        alerts_html = f"""
        <div style="background:#FEF3C7;border:1px solid #FCD34D;border-radius:12px;padding:14px 18px;margin:18px 0">
          <div style="font-weight:700;color:#92400E;margin-bottom:6px">⚠ Committee alerts &amp; actions today</div>
          <ul style="margin:0;padding-left:18px;color:#78350F;font-size:14px">{items}</ul>
        </div>"""

    changes_html = ""
    if daily and not daily.get("skipped"):
        d = daily.get("decision", {})
        longs = [p for p in d.get("positions", []) if p.get("target_weight", 0) > 0]
        chips = "".join(
            f'<span style="display:inline-block;background:#635BFF1A;color:#635BFF;border-radius:6px;'
            f'padding:3px 8px;margin:2px;font-family:monospace;font-size:12px">'
            f'{p["ticker"]} {p["target_weight"]*100:.0f}%</span>'
            for p in sorted(longs, key=lambda x: -x["target_weight"])[:8])
        changes_html = f"""
        <div style="margin:18px 0">
          <div style="font-weight:700;color:#0A2540;margin-bottom:8px">Today's committee allocation</div>
          <div>{chips}</div>
          <div style="color:#697386;font-size:12px;margin-top:8px">Turnover {daily.get('turnover',0):.0%}
             · cost ${daily.get('cost',0):.2f} · status {daily.get('status','—')}</div>
        </div>"""

    html = f"""<!doctype html><html><body style="margin:0;background:#F6F9FC;
      font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">
      <div style="max-width:600px;margin:0 auto;padding:24px">
        <div style="background:linear-gradient(120deg,#635BFF,#4B45C6 40%,#00D4FF);
             border-radius:16px;padding:28px;color:#fff">
          <div style="font-size:13px;opacity:.85;letter-spacing:.5px">QUORUM · DAILY COMMITTEE REPORT</div>
          <div style="font-size:34px;font-weight:800;margin-top:6px">${val:,.2f}</div>
          <div style="font-size:16px;font-weight:600;color:{'#A7F3D0' if ret>=0 else '#FECACA'}">
            {arrow} {_pct(ret)} since inception</div>
          <div style="font-size:12px;opacity:.8;margin-top:4px">{today}</div>
        </div>
        {alerts_html}
        {changes_html}
        <div style="background:#fff;border:1px solid #E6EBF1;border-radius:14px;overflow:hidden;margin:18px 0">
          <div style="padding:12px 16px;font-weight:700;color:#0A2540;border-bottom:1px solid #E6EBF1">
            Current holdings</div>
          <table style="width:100%;border-collapse:collapse;font-size:14px">{holdings_rows}</table>
        </div>
        <div style="color:#697386;font-size:11px;line-height:1.6;margin-top:18px">
          QUORUM is a multi-agent investment-committee simulation. This is <b>decision-support, not
          financial advice</b>, and no real capital is traded (paper portfolio). The committee runs
          daily, re-evaluates fundamentals, momentum, news and macro, and restructures within risk
          limits. Reply STOP to unsubscribe.
        </div>
      </div></body></html>"""
    return subject, html


def _send_resend(to: list[str], subject: str, html: str) -> dict:
    r = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        json={"from": RESEND_FROM, "to": to, "subject": subject, "html": html},
        timeout=30,
    )
    return {"ok": r.status_code in (200, 201), "status": r.status_code, "body": r.text[:300]}


def _send_gmail(to: list[str], subject: str, html: str) -> dict:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = ", ".join(to)
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        s.sendmail(GMAIL_USER, to, msg.as_string())
    return {"ok": True, "status": 200, "body": "sent via gmail"}


def send_report(to: list[str], subject: str, html: str) -> dict:
    if not to:
        return {"ok": False, "reason": "no recipients"}
    if RESEND_API_KEY:
        try:
            return _send_resend(to, subject, html)
        except Exception as e:
            return {"ok": False, "reason": f"resend error: {e}"}
    if GMAIL_USER and GMAIL_APP_PASSWORD:
        try:
            return _send_gmail(to, subject, html)
        except Exception as e:
            return {"ok": False, "reason": f"gmail error: {e}"}
    return {"ok": False, "reason": "no email provider configured (set RESEND_API_KEY or GMAIL_*)"}
