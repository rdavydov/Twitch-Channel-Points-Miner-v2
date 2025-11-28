from datetime import datetime

from TwitchChannelPointsMiner.classes.gql.data.response.Games import Game


class TimeBasedDropDetails:
    def __init__(
        self,
        _id: str,
        name: str,
        end_at: datetime,
        start_at: datetime,
        benefits: list[str],
        required_minutes_watched: int,
        required_subs: int,
    ):
        self.id = _id
        self.name = name
        self.end_at = end_at
        self.start_at = start_at
        self.benefits = benefits
        self.required_minutes_watched = required_minutes_watched
        self.required_subs = required_subs

    def __repr__(self):
        return f"TimeBasedDropDetails({self.__dict__})"


class TimeBasedDropInProgress:
    class SelfEdge:
        def __init__(
            self,
            has_preconditions_met: bool,
            current_minutes_watched: int,
            current_subs: int,
            drop_instance_id: str | None,
            is_claimed: bool,
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
        self_edge: SelfEdge,
    ):
        self.id = _id
        self.name = name
        self.end_at = end_at
        self.start_at = start_at
        self.benefits = benefits
        self.required_minutes_watched = required_minutes_watched
        self.required_subs = required_subs
        self.self_edge = self_edge

    def __repr__(self):
        return f"TimeBasedDropInProgress({self.__dict__})"


class GameDetails(Game):
    def __init__(self, _id: str, slug: str, display_name: str):
        super().__init__(_id)
        self.slug = slug
        self.display_name = display_name

    def __repr__(self):
        return f"GameDetails({self.__dict__})"


class DropCampaignDetails:
    def __init__(
        self,
        _id: str,
        name: str,
        status: str,
        game: GameDetails,
        allow_channel_ids: list[str] | None,
        time_based_drops: list[TimeBasedDropDetails],
    ):
        self.id = _id
        self.name = name
        self.status = status
        self.game = game
        self.allow_channel_ids = allow_channel_ids
        self.time_based_drops = time_based_drops

    def __repr__(self):
        return f"DropCampaignDetails({self.__dict__})"


class DropCampaignDashboard:
    def __init__(self, _id: str, status: str):
        self.id = _id
        self.status = status

    def __repr__(self):
        return f"DropCampaignDashboard({self.__dict__})"


class DropCampaignInProgress:
    def __init__(self, _id: str, time_based_drops: list[TimeBasedDropInProgress]):
        self.id = _id
        self.time_based_drops = time_based_drops

    def __repr__(self):
        return f"DropCampaign({self.__dict__})"


class DropsHighlightServiceAvailableDropsResponse:
    def __init__(self, ids: list[str]):
        self.ids = ids

    def __repr__(self):
        return f"DropsHighlightServiceAvailableDropsResponse({self.__dict__})"


class InventoryResponse:
    def __init__(self, campaigns: list[DropCampaignInProgress] | None):
        self.campaigns = campaigns

    def __repr__(self):
        return f"InventoryResponse({self.__dict__})"


class ViewerDropsDashboardResponse:
    def __init__(self, campaigns: list[DropCampaignDashboard] | None):
        self.campaigns = campaigns

    def __repr__(self):
        return f"ViewerDropsDashboardResponse({self.__dict__})"


class DropCampaignDetailsResponse:
    def __init__(self, campaign: DropCampaignDetails):
        self.campaign = campaign

    def __repr__(self):
        return f"DropCampaignDetailsResponse({self.__dict__})"


class DropsPageClaimDropsResponse:
    def __init__(self, status: str | None, errors: list | None):
        # The type of `errors` is unknown because I couldn't find an instance of it happening
        self.status = status
        self.errors = errors

    def __repr__(self):
        return f"DropsPageClaimDropsResponse({self.__dict__})"
