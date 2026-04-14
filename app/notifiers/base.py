from abc import ABC, abstractmethod


class BaseNotifier(ABC):
    """
    Abstract base class for all notification channels.
    New channels (Discord, Telegram, etc.) simply extend this class.
    """

    @abstractmethod
    def send(self, drops: list[dict]) -> None:
        """
        Sends a notification for the given new drops.

        drops: List of dicts with keys:
          - game: str
          - name: str
          - game_box_art_url: str
          - start_at: str
          - ends_at: str
          - drops: list[dict] with name, image_url, required_minutes
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass
