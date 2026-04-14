import yaml
import sys
from pathlib import Path


def load_config(path: str = "/config/config.yml") -> dict:
    config_path = Path(path)
    if not config_path.exists():
        print(f"[ERROR] Configuration file not found: {path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    _validate(config)
    return config


def _validate(config: dict):
    errors = []

    if not config.get("games"):
        errors.append("No games configured under 'games'")

    notif = config.get("notifications", {})
    email = notif.get("email", {})
    if email.get("enabled"):
        for field in ["smtp_host", "smtp_port", "smtp_user", "smtp_password", "from_address", "to_addresses"]:
            if not email.get(field):
                errors.append(f"notifications.email.{field} is missing")

    if errors:
        print("[ERROR] Configuration errors:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
