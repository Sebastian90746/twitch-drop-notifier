import requests
import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DROPS_API_URL = "https://twitch-drops-api.sunkwi.com/drops"
MAX_RETRIES = 3
RETRY_DELAY = 10  # seconds between retries


class TwitchClient:
    def __init__(self):
        pass

    def get_all_active_drops(self, games: list[str] | None) -> list[dict]:
        """
        Fetches all active drop campaigns.
        If games is None (test mode), returns all campaigns without filtering.
        Otherwise filters by the configured game names.
        Retries on network errors to handle transient DNS/connectivity issues.
        """
        all_campaigns = self._fetch_with_retry()
        if all_campaigns is None:
            return []

        now = datetime.now(timezone.utc)
        active = []

        for campaign in all_campaigns:
            start = _parse_dt(campaign.get("startAt"))
            end = _parse_dt(campaign.get("endAt"))

            if not (start and end and start <= now <= end):
                continue

            # Filter by game name unless in test mode (games=None)
            if games is not None:
                campaign_game = campaign.get("gameDisplayName", "").lower()
                game_names_lower = [g.lower() for g in games]
                matched = any(
                    g in campaign_game or campaign_game in g
                    for g in game_names_lower
                )
                if not matched:
                    continue

            drops = _extract_drops(campaign)

            active.append({
                "game": campaign.get("gameDisplayName", "?"),
                "campaign_id": campaign.get("id") or campaign.get("gameId"),
                "name": _build_campaign_name(campaign),
                "game_box_art_url": campaign.get("gameBoxArtURL", ""),
                "start_at": campaign.get("startAt"),
                "ends_at": campaign.get("endAt"),
                "drops": drops,
            })

        return active

    def _fetch_with_retry(self) -> list | None:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.get(DROPS_API_URL, timeout=15)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                if attempt < MAX_RETRIES:
                    logger.warning(
                        f"Failed to fetch drop campaigns (attempt {attempt}/{MAX_RETRIES}): {e}")
                    logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(
                        f"Failed to fetch drop campaigns after {MAX_RETRIES} attempts: {e}")
        return None


def _build_campaign_name(campaign: dict) -> str:
    rewards = campaign.get("rewards", [])
    if rewards:
        name = rewards[0].get("name")
        if name:
            return name
    return f"{campaign.get('gameDisplayName', '?')} Drop Campaign"


def _extract_drops(campaign: dict) -> list[dict]:
    """
    Extracts all drops including time-based and subscription-based ones.
    """
    drops = []
    for reward in campaign.get("rewards", []):

        # Time-based drops (watch X minutes)
        for tbd in reward.get("timeBasedDrops", []):
            minutes = tbd.get("requiredMinutesWatched", 0)
            required_subs = tbd.get("requiredSubs", 0)
            for benefit in tbd.get("benefitEdges", []):
                b = benefit.get("benefit", {})
                drops.append({
                    "name": b.get("name", "Unknown Drop"),
                    "image_url": b.get("imageAssetURL", ""),
                    "required_minutes": minutes,
                    "required_subs": required_subs,
                    "type": "subscription" if required_subs > 0 else "watch",
                })

        # Event-based drops (e.g. sub-only, no watch time)
        for ebd in reward.get("eventBasedDrops", []):
            required_subs = ebd.get("requiredSubs", 0)
            for benefit in ebd.get("benefitEdges", []):
                b = benefit.get("benefit", {})
                drops.append({
                    "name": b.get("name", "Unknown Drop"),
                    "image_url": b.get("imageAssetURL", ""),
                    "required_minutes": 0,
                    "required_subs": required_subs,
                    "type": "subscription" if required_subs > 0 else "event",
                })

    # Sort by required watch time ascending, then by name ascending
    drops.sort(key=lambda d: (d["required_minutes"], d["name"].lower()))
    return drops


def _parse_dt(dt_str: str | None) -> datetime | None:
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except ValueError:
        return None
