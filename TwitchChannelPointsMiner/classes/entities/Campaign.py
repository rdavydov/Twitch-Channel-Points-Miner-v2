from datetime import datetime

from TwitchChannelPointsMiner.classes.entities.Drop import Drop
from TwitchChannelPointsMiner.classes.Settings import Settings

def parse_datetime(datetime_str):
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"time data '{datetime_str}' does not match format")

class Campaign(object):
    __slots__ = [
        "id",
        "game",
        "name",
        "status",
        "in_inventory",
        "end_at",
        "start_at",
        "dt_match",
        "drops",
        "channels",
    ]

    def __init__(self, dict):
        self.id = dict["id"]
        self.game = dict["game"]
        self.name = dict["name"]
        self.status = dict["status"]
        self.channels = (
            []
            if dict["allow"]["channels"] is None
            else list(map(lambda x: x["id"], dict["allow"]["channels"]))
        )
        self.in_inventory = False

        self.end_at = parse_datetime(dict["endAt"])
        self.start_at = parse_datetime(dict["startAt"])
        self.dt_match = self.start_at < datetime.now() < self.end_at

        self.drops = list(map(lambda x: Drop(x), dict["timeBasedDrops"]))

    def __repr__(self):
        return f"Campaign(id={self.id}, name={self.name}, game={self.game}, in_inventory={self.in_inventory})"

    def __str__(self):
        return (
            f"{self.name}, Game: {self.game['displayName']} - Drops: {len(self.drops)} pcs. - In inventory: {self.in_inventory}"
            if Settings.logger.less
            else self.__repr__()
        )

    def clear_drops(self):
        self.drops = list(
            filter(lambda x: x.dt_match is True and x.is_claimed is False, self.drops)
        )

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.id == other.id
        else:
            return False

    def sync_drops(self, drops, callback):
        # Iterate all the drops from inventory
        for drop in drops:
            # Iterate all the drops from out campaigns array
            # After id match update with:
            # [currentMinutesWatched, hasPreconditionsMet, dropInstanceID, isClaimed]
            for i in range(len(self.drops)):
                current_id = self.drops[i].id
                if drop["id"] == current_id:
                    self.drops[i].update(drop["self"])
                    # If after update we all conditions are meet we can claim the drop
                    if self.drops[i].is_claimable is True:
                        claimed = callback(self.drops[i])
                        self.drops[i].is_claimed = claimed
                    break
