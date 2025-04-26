from datetime import datetime

from TwitchChannelPointsMiner.classes.Settings import Settings
from TwitchChannelPointsMiner.utils import percentage

def parse_datetime(datetime_str):
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"time data '{datetime_str}' does not match format")

class Drop(object):
    __slots__ = [
        "id",
        "name",
        "benefit",
        "minutes_required",
        "has_preconditions_met",
        "current_minutes_watched",
        "drop_instance_id",
        "is_claimed",
        "is_claimable",
        "percentage_progress",
        "end_at",
        "start_at",
        "dt_match",
        "is_printable",
    ]

    def __init__(self, dict):
        self.id = dict["id"]
        self.name = dict["name"]
        self.benefit = ", ".join(
            list(set([bf["benefit"]["name"] for bf in dict["benefitEdges"]]))
        )
        self.minutes_required = dict["requiredMinutesWatched"]

        self.has_preconditions_met = None  # [True, False], None we don't know
        self.current_minutes_watched = 0
        self.drop_instance_id = None
        self.is_claimed = False
        self.is_claimable = False
        self.is_printable = False
        self.percentage_progress = 0

        self.end_at = parse_datetime(dict["endAt"])
        self.start_at = parse_datetime(dict["startAt"])
        self.dt_match = self.start_at < datetime.now() < self.end_at

    def update(
        self,
        progress,
    ):
        self.has_preconditions_met = progress["hasPreconditionsMet"]

        updated_percentage = percentage(
            progress["currentMinutesWatched"], self.minutes_required
        )
        quarter = round((updated_percentage / 25), 4).is_integer()
        self.is_printable = (
            # The new currentMinutesWatched are GT than previous
            progress["currentMinutesWatched"] > self.current_minutes_watched
            and (
                # The drop is printable when we have a new updated values and:
                #  - also the percentage It's different and  quarter is True (self.current_minutes_watched != 0 for skip boostrap phase)
                #  - or we have watched 1 and the previous value is 0 - We are collecting a new drop :)
                (
                    updated_percentage > self.percentage_progress
                    and quarter is True
                    and self.current_minutes_watched != 0
                )
                or (
                    progress["currentMinutesWatched"] == 1
                    and self.current_minutes_watched == 0
                )
            )
        )

        self.current_minutes_watched = progress["currentMinutesWatched"]
        self.drop_instance_id = progress["dropInstanceID"]
        self.is_claimed = progress["isClaimed"]
        self.is_claimable = (
            self.is_claimed is False and self.drop_instance_id is not None
        )
        self.percentage_progress = updated_percentage

    def __repr__(self):
        return f"Drop(id={self.id}, name={self.name}, benefit={self.benefit}, minutes_required={self.minutes_required}, has_preconditions_met={self.has_preconditions_met}, current_minutes_watched={self.current_minutes_watched}, percentage_progress={self.percentage_progress}%, drop_instance_id={self.drop_instance_id}, is_claimed={self.is_claimed})"

    def __str__(self):
        return (
            f"{self.name} ({self.benefit}) {self.current_minutes_watched}/{self.minutes_required} ({self.percentage_progress}%)"
            if Settings.logger.less
            else self.__repr__()
        )

    def progress_bar(self):
        progress = self.percentage_progress // 2
        remaining = (100 - self.percentage_progress) // 2
        if remaining + progress < 50:
            remaining += 50 - (remaining + progress)
        return f"|{('█' * progress)}{(' ' * remaining)}|\t{self.percentage_progress}% [{self.current_minutes_watched}/{self.minutes_required}]"

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.id == other.id
        else:
            return False
