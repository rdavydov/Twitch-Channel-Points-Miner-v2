class Properties:
    class Claim:
        def __init__(self, _id: str):
            self.id = _id

        def __repr__(self):
            return f"Claim({self.__dict__})"

    class Multiplier:
        def __init__(self, factor: float):
            self.factor = factor

        def __repr__(self):
            return f"Multiplier({self.__dict__})"

    def __init__(
        self,
        available_claim: Claim | None,
        balance: int,
        active_multipliers: list[Multiplier],
    ):
        self.available_claim = available_claim
        self.balance = balance
        self.active_multipliers = active_multipliers

    def __repr__(self):
        return f"Properties({self.__dict__})"


class CommunityGoal:
    def __init__(
        self,
        amount_needed: int,
        _id: str,
        is_in_stock: bool,
        per_stream_user_maximum_contribution: int,
        points_contributed: int,
        status: str,
        title: str,
    ):
        self.amount_needed = amount_needed
        self.id = _id
        self.is_in_stock = is_in_stock
        self.per_stream_user_maximum_contribution = per_stream_user_maximum_contribution
        self.points_contributed = points_contributed
        self.status = status
        self.title = title

    def __repr__(self):
        return f"CommunityGoal({self.__dict__})"


class CommunityPointsSettings:
    def __init__(self, goals: list[CommunityGoal]):
        self.goals = goals

    def __repr__(self):
        return f"CommunityPointsSettings({self.goals})"


class Channel:
    class ChannelSelfEdge:
        def __init__(self, community_points: Properties):
            self.community_points = community_points

        def __repr__(self):
            return f"ChannelSelfEdge({self.__dict__})"

    def __init__(
        self,
        _id: str,
        edge: ChannelSelfEdge,
        community_points_settings: CommunityPointsSettings,
    ):
        self.id = _id
        self.edge = edge
        self.community_points_settings = community_points_settings

    def __repr__(self):
        return f"Channel({self.__dict__})"


class CommunityUser:
    def __init__(self, _id: str, display_name: str, channel: Channel):
        self.id = _id
        self.display_name = display_name
        self.channel = channel

    def __repr__(self):
        return f"CommunityUser({self.__dict__})"


class ChannelPointsContextResponse:
    def __init__(self, community: CommunityUser | None):
        self.community = community

    def __repr__(self):
        return f"ChannelPointsContext({self.__dict__})"


class GoalContribution:
    def __init__(self, _id: str, user_points_contributed_this_stream: int):
        self.id = _id
        self.user_points_contributed_this_stream = user_points_contributed_this_stream

    def __repr__(self):
        return f"GoalContribution({self.__dict__})"


class UserPointsContributionResponse:
    def __init__(self, goal_contributions: list[GoalContribution]):
        self.goal_contributions = goal_contributions

    def __repr__(self):
        return f"UserPointsContributionResponse({self.__dict__})"


class ContributeToCommunityGoalResponse:
    def __init__(self, error: str | None):
        self.error = error

    def __repr__(self):
        return f"ContributeToCommunityGoalResponse({self.__dict__})"
