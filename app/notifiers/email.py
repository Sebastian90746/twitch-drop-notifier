import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from pathlib import Path

from .base import BaseNotifier

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).parent.parent / "email_template.html"


class EmailNotifier(BaseNotifier):

    def __init__(self, config: dict):
        self.smtp_host = config["smtp_host"]
        self.smtp_port = config["smtp_port"]
        self.smtp_user = config["smtp_user"]
        self.smtp_password = config["smtp_password"]
        self.from_address = config["from_address"]
        self.to_addresses = config["to_addresses"]

    @property
    def name(self) -> str:
        return "Email"

    def send(self, drops: list[dict]) -> None:
        if not drops:
            return

        subject = self._build_subject(drops)
        html_body = self._build_html(drops)
        text_body = self._build_text(drops)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_address
        msg["To"] = ", ".join(self.to_addresses)

        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_address,
                                self.to_addresses, msg.as_string())
            logger.info(f"Email sent to: {', '.join(self.to_addresses)}")
        except Exception as e:
            logger.error(f"Email error: {e}")

    def _build_subject(self, drops: list[dict]) -> str:
        games = list({d["game"] for d in drops})
        if len(games) == 1:
            return f"Twitch Drops Active: {games[0]}"
        if len(games) > 2:
            return f"Twitch Drops Active: {', '.join(games[:2])} (+{len(games) - 2} more)"
        return f"Twitch Drops Active: {' & '.join(games)}"

    def _build_text(self, drops: list[dict]) -> str:
        lines = ["New active Twitch drop campaigns:\n"]
        for d in drops:
            lines.append(f"{d['game']} - {d['name']}")
            lines.append(
                f"  Period: {_fmt_dt(d['start_at'])} to {_fmt_dt(d['ends_at'])}")
            for item in d.get("drops", []):
                if item["type"] == "subscription":
                    requirement = f"Subscribe x{item['required_subs']}"
                elif item["type"] == "watch":
                    requirement = _fmt_minutes(item["required_minutes"])
                else:
                    requirement = "Event"
                lines.append(f"  - {item['name']} ({requirement})")
            lines.append("")
        lines.append("https://www.twitch.tv/drops/campaigns")
        return "\n".join(lines)

    def _build_html(self, drops: list[dict]) -> str:
        try:
            template = TEMPLATE_PATH.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Could not read email template: {e}")
            return self._build_text(drops)

        campaigns_html = ""
        for d in drops:
            rows = ""
            for item in d.get("drops", []):
                img_tag = (
                    f'<img src="{item["image_url"]}" alt="" style="pointer-events:none;display:block;" />'
                    if item.get("image_url") else ""
                )

                if item["type"] == "subscription":
                    badge = '<span class="badge badge-sub">Subscription required</span>'
                    req = badge
                elif item["type"] == "watch":
                    req = _fmt_minutes(item["required_minutes"])
                else:
                    req = "Event"

                rows += f"""
                <tr>
                  <td>
                    <div class="drop-item">
                      {img_tag}
                      <span>{item["name"]}</span>
                    </div>
                  </td>
                  <td class="watch-time">{req}</td>
                </tr>"""

            drop_table = ""
            if rows:
                drop_table = f"""
                <table class="drops-table">
                  <thead>
                    <tr>
                      <th>Drop</th>
                      <th>Requirement</th>
                    </tr>
                  </thead>
                  <tbody>{rows}</tbody>
                </table>"""

            box_art = ""
            if d.get("game_box_art_url"):
                box_art = f'<img class="box-art" src="{d["game_box_art_url"]}" alt="{d["game"]}" style="pointer-events:none;display:block;" />'

            campaigns_html += f"""
            <div class="campaign">
              <div class="campaign-header">
                {box_art}
                <div class="campaign-meta">
                  <h2>{d["game"]}</h2>
                  <div class="campaign-name">{d["name"]}</div>
                  <div class="campaign-dates">
                    {_fmt_dt(d["start_at"])} &mdash; {_fmt_dt(d["ends_at"])}
                  </div>
                </div>
              </div>
              {drop_table}
            </div>"""

        generated_at = datetime.now(
            timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        html = template.replace(
            "<!-- CAMPAIGNS_PLACEHOLDER -->", campaigns_html)
        html = html.replace("{{generated_at}}", generated_at)
        return html


def _fmt_dt(dt_str: str | None) -> str:
    if not dt_str:
        return "?"
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y %H:%M UTC")
    except ValueError:
        return dt_str


def _fmt_minutes(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    remaining = minutes % 60
    if remaining == 0:
        return f"{hours} h"
    return f"{hours} h {remaining} min"
