import json
import logging
import time
from base64 import b64encode

from TwitchChannelPointsMiner.classes.Settings import Settings
from TwitchChannelPointsMiner.constants import DROP_ID

logger = logging.getLogger(__name__)


class Stream(object):
    __slots__ = [
        "broadcast_id",
        "title",
        "game",
        "tags",
        "drops_tags",
        "campaigns",
        "campaigns_ids",
        "viewers_count",
        "spade_url",
        "payload",
        "watch_streak_missing",
        "minute_watched",
        "__last_update",
        "__minute_watched_timestamp",
    ]

    def __init__(self):
        self.broadcast_id = None

        self.title = None
        self.game = {}
        self.tags = []

        self.drops_tags = False
        self.campaigns = []
        self.campaigns_ids = []

        self.viewers_count = 0
        self.__last_update = 0

        self.spade_url = None
        self.payload = None

        self.init_watch_streak()

    def encode_payload(self) -> dict:
        json_event = json.dumps(self.payload, separators=(",", ":"))
        return {"data": (b64encode(json_event.encode("utf-8"))).decode("utf-8")}

    def update(self, broadcast_id, title, game, tags, viewers_count):
        self.broadcast_id = broadcast_id
        self.title = title.strip()
        self.game = game
        # #343 temporary workaround
        self.tags = tags or []
        # ------------------------
        self.viewers_count = viewers_count

        self.drops_tags = (
            DROP_ID in [tag["id"] for tag in self.tags] and self.game != {}
        )
        self.__last_update = time.time()

        logger.debug(f"Update: {self}")

    def __repr__(self):
        return f"Stream(title={self.title}, game={self.__str_game()}, tags={self.__str_tags()})"

    def __str__(self):
        return f"{self.title}" if Settings.logger.less else self.__repr__()

    def __str_tags(self):
        return (
            None
            if self.tags == []
            else ", ".join([tag["localizedName"] for tag in self.tags])
        )

    def __str_game(self):
        return None if self.game in [{}, None] else self.game["displayName"]

    def game_name(self):
        return None if self.game in [{}, None] else self.game["name"]
    
    def game_id(self):
        return None if self.game in [{}, None] else self.game["id"]

    def update_required(self):
        return self.__last_update == 0 or self.update_elapsed() >= 120

    def update_elapsed(self):
        return 0 if self.__last_update == 0 else (time.time() - self.__last_update)

    def init_watch_streak(self):
        self.watch_streak_missing = True
        self.minute_watched = 0
        self.__minute_watched_timestamp = 0

    def update_minute_watched(self):
        if self.__minute_watched_timestamp != 0:
            self.minute_watched += round(
                (time.time() - self.__minute_watched_timestamp) / 60, 5
            )
        self.__minute_watched_timestamp = time.time()
