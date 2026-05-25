import csv
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

LOG_FILE = Path("/data/drop_log.csv")

HEADERS = [
    "first_seen",
    "game",
    "game_id",
    "campaign",
    "item_name",
    "benefit_id",
    "tbd_id",
    "type",
    "requirement",
    "campaign_start",
    "campaign_end",
]


def _item_key(game_id: str, tbd_id: str, benefit_id: str, start_at: str) -> str:
    """
    Unique key per drop entry: gameId + tbd_id + benefit_id + campaign start.

    tbd_id (timeBasedDrop ID) is required as tiebreaker because some games
    reuse the same benefit_id across multiple watch-time milestones or even
    for different items (confirmed against live API data).
    """
    return f"{game_id}|{tbd_id}|{benefit_id}|{start_at}"


def _load_seen_keys() -> set:
    if not LOG_FILE.exists():
        return set()
    seen = set()
    try:
        with open(LOG_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = _item_key(
                    row.get("game_id", ""),
                    row.get("tbd_id", ""),
                    row.get("benefit_id", ""),
                    row.get("campaign_start", ""),
                )
                seen.add(key)
    except Exception as e:
        logger.error(f"Failed to read drop log: {e}")
    return seen


def _fmt_requirement(drop: dict) -> str:
    if drop["type"] == "subscription":
        return f"sub x{drop['required_subs']}"
    elif drop["type"] == "watch":
        minutes = drop["required_minutes"]
        if minutes < 60:
            return f"{minutes} min"
        hours = minutes // 60
        remaining = minutes % 60
        return f"{hours} h {remaining} min" if remaining else f"{hours} h"
    return "event"


def log_new_drops(campaigns: list[dict]):
    """
    Appends newly found drops to the CSV log.
    Unique key: game_id + tbd_id + benefit_id + campaign_start.
    Returns the number of new rows written.
    """
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    write_header = not LOG_FILE.exists() or LOG_FILE.stat().st_size == 0
    seen_keys = _load_seen_keys()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    new_rows = 0
    try:
        with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            if write_header:
                writer.writeheader()

            for campaign in campaigns:
                game_id = campaign.get("game_id", "")
                start_at = campaign.get("start_at", "")

                for drop in campaign.get("drops", []):
                    benefit_id = drop.get("benefit_id", "")
                    tbd_id = drop.get("tbd_id", "")
                    key = _item_key(game_id, tbd_id, benefit_id, start_at)

                    if key in seen_keys:
                        continue

                    writer.writerow({
                        "first_seen": now,
                        "game": campaign["game"],
                        "game_id": game_id,
                        "campaign": campaign["name"],
                        "item_name": drop["name"],
                        "benefit_id": benefit_id,
                        "tbd_id": tbd_id,
                        "type": drop["type"],
                        "requirement": _fmt_requirement(drop),
                        "campaign_start": start_at,
                        "campaign_end": campaign.get("ends_at", ""),
                    })
                    seen_keys.add(key)
                    new_rows += 1

    except Exception as e:
        logger.error(f"Failed to write drop log: {e}")

    if new_rows:
        logger.info(f"Drop log: {new_rows} new item(s) written to {LOG_FILE}")
    else:
        logger.debug("Drop log: no new items to write")

    return new_rows
