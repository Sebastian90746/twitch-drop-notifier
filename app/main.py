import time
import json
import logging
from pathlib import Path

from config import load_config
from twitch import TwitchClient
from notifiers import EmailNotifier
from drop_log import log_new_drops

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


def log_campaign_summary(campaign: dict, status: str):
    """Logs a structured summary of a campaign and its drops."""
    logger = logging.getLogger(__name__)
    drops = campaign.get("drops", [])
    ends = campaign.get("ends_at", "?")[:10]

    logger.info(f"  [{status}] {campaign['game']} — {campaign['name']} (until {ends})")
    if drops:
        for drop in drops:
            if drop["type"] == "subscription":
                req = f"sub x{drop['required_subs']}"
            elif drop["type"] == "watch":
                req = _fmt_minutes(drop["required_minutes"])
            else:
                req = "event"
            logger.info(f"           • {drop['name']} ({req})")
    else:
        logger.info(f"           • (no drop details available)")


def check_drops(client: TwitchClient, games: list[str], seen: set, test_mode: bool) -> tuple[list, list, set]:
    """
    Returns:
      - new_drops:  campaigns to notify about (filtered by games, not yet seen)
      - all_active: all active campaigns regardless of game filter (for logging)
      - seen:       updated seen set
    """
    logger = logging.getLogger(__name__)
    logger.info("Fetching all active drop campaigns...")

    if test_mode:
        all_active = client.get_all_active_drops(games=None)
        logger.debug(f"Test mode: received {len(all_active)} total campaigns from API (unfiltered)")
        for campaign in all_active:
            log_campaign_summary(campaign, "TEST")
        return all_active, all_active, seen

    # Always fetch everything for the log
    all_active = client.get_all_active_drops(games=None)
    # Filter to configured games for notifications
    monitored = client.get_all_active_drops(games=games)

    logger.info(f"Active campaigns total: {len(all_active)} — monitored games: {len(monitored)}")

    new_drops = []
    for campaign in monitored:
        cid = campaign["campaign_id"]
        if cid and cid not in seen:
            log_campaign_summary(campaign, "NEW")
            new_drops.append(campaign)
            seen.add(cid)
        elif cid:
            log_campaign_summary(campaign, "KNOWN")

    return new_drops, all_active, seen


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
        logger.info("All games with active drops will be returned (game filter ignored)")
        logger.info("State will not be saved - every run sends notifications")
        logger.info(f"Configured games (reference only): {', '.join(games)}")
        logger.info("Check interval forced to: 1 minute")
        logger.info("Log level forced to: DEBUG")
    else:
        logger.info("=== Twitch Drop Notifier started ===")
        logger.info(f"Monitored games: {', '.join(games)}")
        logger.info(f"Check interval: {configured_interval} minutes")

    seen = set() if test_mode else load_state()
    if not test_mode:
        logger.info(f"Known campaigns from state: {len(seen)}")

    while True:
        logger.info("--- Starting drop check ---")
        new_drops, all_active, seen = check_drops(client, games, seen, test_mode)

        # Always log all active drops to CSV regardless of game filter
        if not test_mode:
            log_new_drops(all_active)

        if new_drops:
            logger.info(f"{len(new_drops)} new campaign(s) for monitored games — sending notifications")
            for notifier in notifiers:
                try:
                    notifier.send(new_drops)
                    logger.debug(f"Notifier '{notifier.name}' completed successfully")
                except Exception as e:
                    logger.error(f"Notifier {notifier.name} failed: {e}")
            if not test_mode:
                save_state(seen)
        else:
            logger.info("No new campaigns for monitored games")

        next_check = "1 minute [TEST MODE]" if test_mode else f"{configured_interval} minutes"
        logger.info(f"Next check in {next_check}")
        time.sleep(interval)


def _fmt_minutes(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    remaining = minutes % 60
    if remaining == 0:
        return f"{hours} h"
    return f"{hours} h {remaining} min"


if __name__ == "__main__":
    main()