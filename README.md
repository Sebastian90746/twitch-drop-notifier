# Twitch Drop Notifier

A lightweight Docker service that monitors Twitch drop campaigns for your favorite games and sends you an email notification the moment a new campaign goes live.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg)
![Python](https://img.shields.io/badge/python-3.12-3776AB.svg)

---

## Features

- Monitors multiple games simultaneously
- Sends clean HTML emails with game art, drop rewards, and required watch times
- Remembers already-notified campaigns — no duplicate emails
- Configurable check interval
- Extensible notifier system (Discord, Telegram, etc. can be added easily)
- No Twitch developer account required

## How It Works

The service polls the [twitch-drops-api](https://github.com/SunkwiBOT/twitch-drops-api) at a configurable interval, filters results by your configured games, and sends an email for any campaign it hasn't seen before. Seen campaign IDs are persisted in a Docker volume so they survive restarts.

## Requirements

- Docker & Docker Compose
- An email account with SMTP access (e.g. Gmail with an App Password)

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/twitch-drop-notifier.git
cd twitch-drop-notifier
```

### 2. Configure

Copy the example config and fill in your values:

```bash
cp config.yml.example config.yml
```

```yaml
# Games to monitor (exact names as shown on Twitch)
games:
  - "Rust"
  - "Path of Exile 2"
  - "World of Warcraft"

# How often to check for new campaigns (in minutes)
check_interval_minutes: 30

notifications:
  email:
    enabled: true
    smtp_host: "smtp.gmail.com"
    smtp_port: 587
    smtp_user: "you@gmail.com"
    smtp_password: "your_app_password"
    from_address: "you@gmail.com"
    to_addresses:
      - "recipient@example.com"
```

> **Gmail users:** You need to create an [App Password](https://myaccount.google.com/apppasswords) (requires 2FA to be enabled). Use this 16-character password as `smtp_password`.

### 3. Start

```bash
docker compose up -d
```

### 4. Check logs

```bash
docker compose logs -f
```

### 5. Stop

```bash
docker compose down
```

## Email Preview

Each notification includes:

- Game box art
- Campaign name and duration
- A table of all available drops with their item image and required watch time

## Project Structure

```
twitch-drop-notifier/
├── docker-compose.yml
├── Dockerfile
├── config.yml            # Your configuration (not committed)
├── config.yml.example    # Example configuration
└── app/
    ├── main.py           # Main loop
    ├── twitch.py         # API client
    ├── config.py         # Config loader & validation
    ├── email_template.html
    └── notifiers/
        ├── base.py       # Abstract notifier base class
        └── email.py      # Email notifier
```

## Adding More Notifiers

New notification channels can be added by creating a class in `app/notifiers/` that extends `BaseNotifier` and implements the `send(drops)` method, then enabling it in `main.py`.

```python
# app/notifiers/discord.py
from .base import BaseNotifier

class DiscordNotifier(BaseNotifier):
    def __init__(self, config: dict):
        self.webhook_url = config["webhook_url"]

    @property
    def name(self) -> str:
        return "Discord"

    def send(self, drops: list[dict]) -> None:
        # post to self.webhook_url
        ...
```

## Data Source

Drop campaign data is sourced from the community-maintained [twitch-drops-api](https://github.com/SunkwiBOT/twitch-drops-api). This project is not affiliated with Twitch.

## License

MIT