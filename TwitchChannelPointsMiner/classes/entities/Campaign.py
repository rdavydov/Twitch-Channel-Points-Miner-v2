from datetime import datetime
from typing import Callable

from TwitchChannelPointsMiner.classes.Settings import Settings
from TwitchChannelPointsMiner.classes.entities.Drop import Drop
from TwitchChannelPointsMiner.classes.gql.data.response.Drops import (
    TimeBasedDropInProgress,
    DropCampaignDetails,
)


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

    def __init__(self, data: DropCampaignDetails):
        self.id = data.id
        self.game = data.game
        self.name = data.name
        self.status = data.status
        self.channels = (
            data.allow_channel_ids if data.allow_channel_ids is not None else []
        )
        self.end_at = data.end_at
        self.start_at = data.start_at
        self.dt_match = self.start_at < datetime.now() < self.end_at
        self.in_inventory = False
        self.drops = [Drop(drop) for drop in data.time_based_drops]

    def __repr__(self):
        return f"Campaign(id={self.id}, name={self.name}, game={self.game}, in_inventory={self.in_inventory})"

    def __str__(self):
        return (
            f"{self.name}, Game: {self.game.display_name} - Drops: {len(self.drops)} pcs. - In inventory: {self.in_inventory}"
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

    def sync_drops(
        self, drops: list[TimeBasedDropInProgress], callback: Callable[[Drop], bool]
    ):
        # Iterate all the drops from inventory
        for drop in drops:
            # Iterate all the drops from out campaigns array
            # After id match update with:
            # [currentMinutesWatched, hasPreconditionsMet, dropInstanceID, isClaimed]
            for i in range(len(self.drops)):
                current_id = self.drops[i].id
                if drop.id == current_id:
                    self.drops[i].update(drop.self_edge)
                    # If after update we all conditions are meet we can claim the drop
                    if self.drops[i].is_claimable:
                        claimed = callback(self.drops[i])
                        self.drops[i].is_claimed = claimed
                    break
