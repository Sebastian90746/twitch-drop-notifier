import time
import json
import logging
from pathlib import Path

from config import load_config
from twitch import TwitchClient
from notifiers import EmailNotifier

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
        logging.getLogger(__name__).info("Notifier loaded: Email")

    # Add further notifiers here later:
    # if notif_cfg.get("discord", {}).get("enabled"):
    #     from notifiers.discord import DiscordNotifier
    #     notifiers.append(DiscordNotifier(notif_cfg["discord"]))

    return notifiers


def check_drops(client: TwitchClient, games: list[str], seen: set, test_mode: bool) -> tuple[list, set]:
    logger = logging.getLogger(__name__)
    logger.info("Fetching all active drop campaigns...")

    if test_mode:
        # In test mode: return ALL games that have active drops, ignore filter
        all_drops = client.get_all_active_drops(games=None)
        logger.debug(
            f"Test mode: received {len(all_drops)} total campaigns from API (unfiltered)")
    else:
        all_drops = client.get_all_active_drops(games=games)

    if not all_drops:
        logger.info("No active campaigns found")
        return [], seen

    new_drops = []
    for campaign in all_drops:
        cid = campaign["campaign_id"]
        if test_mode:
            # In test mode: always treat every campaign as new, never persist state
            logger.debug(
                f"  [TEST] [{campaign['game']}] {campaign['name']} — {len(campaign['drops'])} drop(s)")
            new_drops.append(campaign)
        elif cid and cid not in seen:
            logger.info(f"  -> New: [{campaign['game']}] {campaign['name']}")
            new_drops.append(campaign)
            seen.add(cid)
        elif cid:
            logger.info(
                f"  -> Already known: [{campaign['game']}] {campaign['name']}")

    return new_drops, seen


def main():
    config = load_config()
    test_mode = config.get("test_mode", False)

    log_level = logging.DEBUG if test_mode else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(__name__)

    games = config["games"]
    configured_interval = config.get("check_interval_minutes", 30)
    interval = (1 if test_mode else configured_interval) * 60

    client = TwitchClient()
    notifiers = build_notifiers(config)

    if not notifiers:
        logger.warning("No notifiers enabled - please check config.yml")

    if test_mode:
        logger.info("=== Twitch Drop Notifier started [TEST MODE] ===")
        logger.info(
            "All games with active drops will be returned (game filter ignored)")
        logger.info("State will not be saved - every run sends notifications")
        logger.info(f"Configured games (reference only): {', '.join(games)}")
        logger.info("Check interval forced to: 1 minute")
        logger.info("Log level forced to: DEBUG")
    else:
        logger.info("=== Twitch Drop Notifier started ===")
        logger.info(f"Monitored games: {', '.join(games)}")
        logger.info(f"Check interval: {configured_interval} minutes")
        seen = load_state()
        logger.info(f"Known campaigns from state: {len(seen)}")

    seen = set() if test_mode else load_state()

    while True:
        logger.info("--- Starting drop check ---")
        new_drops, seen = check_drops(client, games, seen, test_mode)

        if new_drops:
            logger.info(
                f"{len(new_drops)} campaign(s) found - sending notifications")
            for notifier in notifiers:
                try:
                    notifier.send(new_drops)
                    logger.debug(
                        f"Notifier '{notifier.name}' completed successfully")
                except Exception as e:
                    logger.error(f"Notifier {notifier.name} failed: {e}")
            if not test_mode:
                save_state(seen)
        else:
            logger.info("No campaigns found")

        next_check = "1 minute [TEST MODE]" if test_mode else f"{configured_interval} minutes"
        logger.info(f"Next check in {next_check}")
        time.sleep(interval)


if __name__ == "__main__":
    main()
