import time
import json
import logging
from pathlib import Path

from config import load_config
from twitch import TwitchClient
from notifiers import EmailNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

STATE_FILE = Path("/data/seen_campaigns.json")


def load_state() -> set:
    if STATE_FILE.exists():
        try:
            return set(json.loads(STATE_FILE.read_text()))
        except Exception:
            pass
    return set()


def save_state(seen: set):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(list(seen)))


def build_notifiers(config: dict) -> list:
    notifiers = []
    notif_cfg = config.get("notifications", {})

    if notif_cfg.get("email", {}).get("enabled"):
        notifiers.append(EmailNotifier(notif_cfg["email"]))
        logger.info("Notifier loaded: Email")

    # Add further notifiers here later:
    # if notif_cfg.get("discord", {}).get("enabled"):
    #     from notifiers.discord import DiscordNotifier
    #     notifiers.append(DiscordNotifier(notif_cfg["discord"]))

    return notifiers


def check_drops(client: TwitchClient, games: list[str], seen: set) -> tuple[list, set]:
    logger.info("Fetching all active drop campaigns...")
    all_drops = client.get_all_active_drops(games)

    if not all_drops:
        logger.info("No active campaigns found for configured games")

    new_drops = []
    for campaign in all_drops:
        cid = campaign["campaign_id"]
        if cid and cid not in seen:
            logger.info(f"  -> New: [{campaign['game']}] {campaign['name']}")
            new_drops.append(campaign)
            seen.add(cid)
        elif cid:
            logger.info(
                f"  -> Already known: [{campaign['game']}] {campaign['name']}")

    return new_drops, seen


def main():
    logger.info("=== Twitch Drop Notifier started ===")

    config = load_config()
    games = config["games"]
    interval = config.get("check_interval_minutes", 30) * 60

    client = TwitchClient()

    notifiers = build_notifiers(config)
    if not notifiers:
        logger.warning("No notifiers enabled - please check config.yml")

    logger.info(f"Monitored games: {', '.join(games)}")
    logger.info(
        f"Check interval: {config.get('check_interval_minutes', 30)} minutes")

    seen = load_state()
    logger.info(f"Known campaigns from state: {len(seen)}")

    while True:
        logger.info("--- Starting drop check ---")
        new_drops, seen = check_drops(client, games, seen)

        if new_drops:
            logger.info(
                f"{len(new_drops)} new campaign(s) found - sending notifications")
            for notifier in notifiers:
                try:
                    notifier.send(new_drops)
                except Exception as e:
                    logger.error(f"Notifier {notifier.name} failed: {e}")
            save_state(seen)
        else:
            logger.info("No new campaigns")

        logger.info(
            f"Next check in {config.get('check_interval_minutes', 30)} minutes")
        time.sleep(interval)


if __name__ == "__main__":
    main()
