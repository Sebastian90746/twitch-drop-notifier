import requests
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DROPS_API_URL = "https://twitch-drops-api.sunkwi.com/drops"


class TwitchClient:
    def __init__(self):
        pass

    def get_all_active_drops(self, games: list[str]) -> list[dict]:
        """
        Fetches all active drop campaigns and filters by configured games.
        """
        try:
            resp = requests.get(DROPS_API_URL, timeout=15)
            resp.raise_for_status()
            all_campaigns = resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch drop campaigns: {e}")
            return []

        now = datetime.now(timezone.utc)
        game_names_lower = [g.lower() for g in games]
        active = []

        for campaign in all_campaigns:
            campaign_game = campaign.get("gameDisplayName", "").lower()

            matched = any(
                g in campaign_game or campaign_game in g
                for g in game_names_lower
            )
            if not matched:
                continue

            start = _parse_dt(campaign.get("startAt"))
            end = _parse_dt(campaign.get("endAt"))

            if not (start and end and start <= now <= end):
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


def _build_campaign_name(campaign: dict) -> str:
    rewards = campaign.get("rewards", [])
    if rewards:
        name = rewards[0].get("name")
        if name:
            return name
    return f"{campaign.get('gameDisplayName', '?')} Drop Campaign"


def _extract_drops(campaign: dict) -> list[dict]:
    """
    Extracts all individual drops with name, image and required watch time.
    """
    drops = []
    for reward in campaign.get("rewards", []):
        for tbd in reward.get("timeBasedDrops", []):
            minutes = tbd.get("requiredMinutesWatched", 0)
            for benefit in tbd.get("benefitEdges", []):
                b = benefit.get("benefit", {})
                drops.append({
                    "name": b.get("name", "Unknown Drop"),
                    "image_url": b.get("imageAssetURL", ""),
                    "required_minutes": minutes,
                })
    return drops


def _parse_dt(dt_str: str | None) -> datetime | None:
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except ValueError:
        return None
