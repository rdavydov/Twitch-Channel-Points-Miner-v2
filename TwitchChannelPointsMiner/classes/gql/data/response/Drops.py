from datetime import datetime


class DropsHighlightServiceAvailableDropsResponse:
    def __init__(self, ids: list[str]):
        self.ids = ids

    def __repr__(self):
        return f"DropsHighlightServiceAvailableDropsResponse({self.__dict__})"


class TimeBasedDrop:
    class SelfEdge:
        def __init__(
            self,
            has_preconditions_met: bool,
            current_minutes_watched: int,
            current_subs: int,
            drop_instance_id: str | None,
            is_claimed: bool
        ):
            self.has_preconditions_met = has_preconditions_met
            self.current_minutes_watched = current_minutes_watched
            self.current_subs = current_subs
            self.drop_instance_id = drop_instance_id
            self.is_claimed = is_claimed

        def __repr__(self):
            return f"SelfEdge({self.__dict__})"

    def __init__(
        self,
        _id: str,
        name: str,
        end_at: datetime,
        start_at: datetime,
        benefits: list[str],
        required_minutes_watched: int,
        required_subs: int,
        self_edge: SelfEdge
    ):
        self._id = _id
        self.name = name
        self.end_at = end_at
        self.start_at = start_at
        self.benefits = benefits
        self.required_minutes_watched = required_minutes_watched
        self.required_subs = required_subs
        self.self_edge = self_edge

    def __repr__(self):
        return f"TimeBasedDrop({self.__dict__})"


class Game:
    def __init__(self, _id: str, slug: str, name: str, box_art_url: str | None):
        self._id = _id
        self.slug = slug
        self.name = name
        self.box_art_url = box_art_url

    def __repr__(self):
        return f"Game({self.__dict__})"


class DropCampaign:
    def __init__(self, _id: str, status: str, game: Game, time_based_drops: list[TimeBasedDrop]):
        self.id = _id
        self.status = status
        self.game = game
        self.time_based_drops = time_based_drops

    def __repr__(self):
        return f"DropCampaign({self.__dict__})"


class InventoryResponse:
    def __init__(self, campaigns: list[DropCampaign] | None):
        self.campaigns = campaigns

    def __repr__(self):
        return f"InventoryResponse({self.__dict__})"


class ViewerDropsDashboardResponse:
    def __init__(self, campaigns: list[DropCampaign] | None):
        self.campaigns = campaigns

    def __repr__(self):
        return f"ViewerDropsDashboardResponse({self.__dict__})"


class DropCampaignDetailsResponse:
    def __init__(self, campaign: DropCampaign):
        self.campaign = campaign

    def __repr__(self):
        return f"DropCampaignDetailsResponse({self.__dict__})"


class DropsPageClaimDropsResponse:
    def __init__(self, status: str):
        self.status = status

    def __repr__(self):
        return f"DropsPageClaimDropsResponse({self.__dict__})"
