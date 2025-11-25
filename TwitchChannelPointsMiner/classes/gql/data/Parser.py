import datetime
from typing import Callable, Any, ContextManager

from TwitchChannelPointsMiner.classes.gql.Errors import InvalidJsonShapeException, GQLResponseErrors
from TwitchChannelPointsMiner.classes.gql.data.response import (
    ChannelPointsContext, Predictions, Drops,
    PlaybackAccessToken
)
from TwitchChannelPointsMiner.classes.gql.data.response.BroadcastSettings import BroadcastSettings, Game
from TwitchChannelPointsMiner.classes.gql.data.response.ChannelFollows import ChannelFollowsResponse, Follow
from TwitchChannelPointsMiner.classes.gql.data.response.ChannelPointsContext import ChannelPointsContextResponse
from TwitchChannelPointsMiner.classes.gql.data.response.Drops import (
    DropsHighlightServiceAvailableDropsResponse,
    InventoryResponse
)
from TwitchChannelPointsMiner.classes.gql.data.response.Error import Error
from TwitchChannelPointsMiner.classes.gql.data.response.GetIdFromLogin import GetIdFromLoginResponse
from TwitchChannelPointsMiner.classes.gql.data.response.Pagination import PageInfo, Paginated, Edge
from TwitchChannelPointsMiner.classes.gql.data.response.PlaybackAccessToken import PlaybackAccessTokenResponse
from TwitchChannelPointsMiner.classes.gql.data.response.Stream import Stream, Tag
from TwitchChannelPointsMiner.classes.gql.data.response.VideoPlayerStreamInfoOverlayChannel import (
    User,
    VideoPlayerStreamInfoOverlayChannelResponse
)


class JsonParentContext(ContextManager):
    """Context Manager that appends the parent name to InvalidJsonShapeExceptions"""

    def __init__(self, name: str | int):
        self.name = name

    def __exit__(self, exc_type, exc_val, exc_tb):
        if isinstance(exc_val, InvalidJsonShapeException):
            exc_val.path.append(self.name)


def identity(x):
    return x


def expect_dict(value: Any) -> dict:
    if not isinstance(value, dict):
        raise InvalidJsonShapeException([], "dict expected")
    return value


def expect_list(value: Any) -> list:
    if not isinstance(value, list):
        raise InvalidJsonShapeException([], "list expected")
    return value


def expect_str(value: Any) -> str:
    if not isinstance(value, str):
        raise InvalidJsonShapeException([], "str expected")
    return value


def expect_int(value: Any) -> int:
    if not isinstance(value, int):
        raise InvalidJsonShapeException([], "int expected")
    return value


def expect_bool(value: Any) -> bool:
    if not isinstance(value, bool):
        raise InvalidJsonShapeException([], "bool expected")
    return value


def expect_iso_8601(value: Any) -> datetime.datetime:
    if not isinstance(value, str):
        raise InvalidJsonShapeException([], "str expected")

    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise InvalidJsonShapeException([], f"time data '{value}' does not match format")


def parse_expected_value[T](source: dict, property_name: str, type_parser: Callable[[Any], T]) -> T:
    if property_name not in source:
        raise InvalidJsonShapeException([property_name], "value should not be None")
    with JsonParentContext(property_name):
        return type_parser(source[property_name])


def parse_value[T](source: dict, property_name: str, type_parser: Callable, default: T | None = None) -> T:
    if property_name not in source:
        return default
    with JsonParentContext(property_name):
        return type_parser(source[property_name])


def list_parser[T](value_type_parser: Callable[[Any], T]) -> Callable[[Any], list[T]]:
    def inner_parser(source: Any) -> T:
        expect_list(source)

        for index, item in enumerate(source):
            with JsonParentContext(index):
                source[index] = value_type_parser(item)
        return source

    return inner_parser


def optional_parser[T](value_type_parser: Callable[[Any], T]) -> Callable[[Any], T | None]:
    def inner_parser(value: Any):
        if value is None:
            return None
        else:
            return value_type_parser(value)

    return inner_parser


def dig[T](value: Any, path: list[str], and_then: Callable[[Any], T]) -> T:
    """
    Utility to "dig" down into a JSON structure using a list of property names.
    :param value: The root value.
    :param path: The path to find.
    :param and_then: What to do with the value once found.
    :return: The value at the end of the path.
    """
    if len(path) == 0:
        return and_then(value)
    expect_dict(value)
    next_value = parse_expected_value(value, path[0], expect_dict)
    with JsonParentContext(path[0]):
        return dig(next_value, path[1:], and_then)


def error_parser(value: Any) -> Error:
    expect_dict(value)
    message = parse_expected_value(value, "message", expect_str)
    recoverable = message in ['service timeout']
    return Error(
        recoverable,
        message,
        parse_value(value, "path", list_parser(expect_str))
    )


def page_info_parser(value: Any) -> PageInfo:
    return PageInfo(
        has_next_page=parse_expected_value(value, "hasNextPage", expect_bool),
        start_cursor=parse_value(value, "startCursor", expect_str),
        end_cursor=parse_value(value, "endCursor", expect_str)
    )


def paginated_parser[T](value_parser: Callable[[Any], T]) -> Callable[[Any], Paginated[T]]:
    """
    Gets a parser for Paginated values.
    :param value_parser: The parser for the `node` of the paginated data.
    :return: The Paginated data.
    """

    def edge_parser(edge: Any) -> Edge[T]:
        cursor = parse_expected_value(edge, "cursor", expect_str)
        node = parse_expected_value(edge, "node", value_parser)
        return Edge(cursor, node)

    def inner_parser(container: Any) -> Paginated[T]:
        edges = parse_expected_value(container, "edges", list_parser(edge_parser))
        page_info = parse_expected_value(container, "pageInfo", page_info_parser)
        return Paginated(edges, page_info)

    return inner_parser


def tag_parser(value: Any) -> Tag:
    expect_dict(value)
    return Tag(
        _id=parse_expected_value(value, "id", expect_str),
    )


def game_parser(value: Any) -> Game:
    expect_dict(value)
    return Game(
        _id=parse_expected_value(value, "id", expect_str),
        display_name=parse_expected_value(value, "displayName", expect_str),
        name=parse_expected_value(value, "name", expect_str),
    )


def broadcast_settings_parser(value: Any) -> BroadcastSettings:
    expect_dict(value)
    return BroadcastSettings(
        _id=parse_expected_value(value, "id", expect_str),
        title=parse_expected_value(value, "title", expect_str),
        game=parse_expected_value(value, "game", game_parser),
    )


def stream_parser(value: Any) -> Stream:
    expect_dict(value)
    return Stream(
        _id=parse_expected_value(value, "id", expect_str),
        viewers_count=parse_expected_value(value, "viewersCount", expect_int),
        tags=parse_expected_value(value, "tags", list_parser(tag_parser)),
    )


def user_parser(value: Any) -> User:
    expect_dict(value)
    _id = parse_expected_value(value, "id", expect_str)
    profile_url = parse_expected_value(value, "profileURL", expect_str)
    display_name = parse_expected_value(value, "displayName", expect_str)
    login = parse_expected_value(value, "login", expect_str)
    profile_image_url = parse_expected_value(value, "profileImageURL", expect_str)
    broadcast_settings = parse_expected_value(value, "broadcastSettings", broadcast_settings_parser)
    stream = parse_value(value, "stream", optional_parser(stream_parser))
    return User(
        _id=_id,
        profile_url=profile_url,
        display_name=display_name,
        login=login,
        profile_image_url=profile_image_url,
        broadcast_settings=broadcast_settings,
        stream=stream,
    )


def follow_self_follower_parser(value: Any) -> Follow.SelfEdge.Follower:
    expect_dict(value)
    return Follow.SelfEdge.Follower(
        disable_notifications=parse_expected_value(value, "disableNotifications", expect_bool),
        followed_at=parse_expected_value(value, "followedAt", expect_iso_8601),
    )


def follow_self_edge_parser(value: Any) -> Follow.SelfEdge:
    expect_dict(value)
    return Follow.SelfEdge(
        can_follow=parse_expected_value(value, "canFollow", expect_bool),
        follower=parse_expected_value(value, "follower", follow_self_follower_parser),
    )


def follow_parser(value: Any) -> Follow:
    expect_dict(value)
    return Follow(
        _id=parse_expected_value(value, "id", expect_str),
        banner_image_url=parse_expected_value(value, "bannerImageURL", optional_parser(expect_str)),
        display_name=parse_expected_value(value, "displayName", expect_str),
        login=parse_expected_value(value, "login", expect_str),
        profile_image_url=parse_expected_value(value, "profileImageURL", expect_str),
        _self=parse_expected_value(value, "self", follow_self_edge_parser),
    )


def authorization_parser(value: Any) -> PlaybackAccessToken.Authorization:
    expect_dict(value)
    return PlaybackAccessToken.Authorization(
        is_forbidden=parse_expected_value(value, "isForbidden", expect_bool),
        forbidden_reason_code=parse_expected_value(value, "forbiddenReasonCode", expect_str)
    )


def claim_parser(value: Any):
    expect_dict(value)
    return ChannelPointsContext.Properties.Claim(
        _id=parse_expected_value(value, "id", expect_str),
    )


def multiplier_parser(value: Any):
    expect_dict(value)
    return ChannelPointsContext.Properties.Multiplier(
        factor=parse_expected_value(value, "factor", float),
    )


def community_points_parser(value: Any):
    expect_dict(value)
    return ChannelPointsContext.Properties(
        available_claim=parse_expected_value(value, "availableClaim", optional_parser(claim_parser)),
        balance=parse_expected_value(value, "balance", expect_int),
        active_multipliers=parse_expected_value(value, "activeMultipliers", list_parser(multiplier_parser))
    )


def channel_self_edge_parser(value: Any):
    expect_dict(value)
    return ChannelPointsContext.Channel.ChannelSelfEdge(
        community_points=parse_expected_value(value, "communityPoints", community_points_parser),
    )


def community_goal_parser(value: Any):
    expect_dict(value)
    return ChannelPointsContext.CommunityGoal(
        amount_needed=parse_expected_value(value, "amountNeeded", expect_int),
        _id=parse_expected_value(value, "id", expect_str),
        is_in_stock=parse_expected_value(value, "isInStock", expect_bool),
        per_stream_user_maximum_contribution=parse_expected_value(
            value, "perStreamUserMaximumContribution", expect_int
        ),
        points_contributed=parse_expected_value(value, "pointsContributed", expect_int),
        status=parse_expected_value(value, "status", expect_str),
        title=parse_expected_value(value, "title", expect_str),
    )


def community_points_settings_parser(value: Any):
    expect_dict(value)
    return ChannelPointsContext.CommunityPointsSettings(
        goals=parse_expected_value(value, "goals", list_parser(community_goal_parser))
    )


def channel_parser(value: Any) -> ChannelPointsContext.Channel:
    expect_dict(value)
    return ChannelPointsContext.Channel(
        _id=parse_expected_value(value, "id", expect_str),
        edge=parse_expected_value(value, "self", channel_self_edge_parser),
        community_points_settings=parse_expected_value(
            value,
            "communityPointsSettings",
            community_points_settings_parser
        )
    )


def community_parser(value: Any) -> ChannelPointsContext.CommunityUser:
    expect_dict(value)
    return ChannelPointsContext.CommunityUser(
        _id=parse_expected_value(value, "id", expect_str),
        display_name=parse_expected_value(value, "displayName", expect_str),
        channel=parse_expected_value(value, "channel", channel_parser),
    )


def prediction_error_parser(value: Any):
    expect_dict(value)
    return Predictions.Error(
        code=parse_expected_value(value, "code", expect_str),
    )


def time_based_drop_self_edge_parser(value: Any):
    expect_dict(value)
    return Drops.TimeBasedDrop.SelfEdge(
        has_preconditions_met=parse_expected_value(value, "hasPreconditionsMet", expect_bool),
        current_minutes_watched=parse_expected_value(value, "currentMinutesWatched", expect_int),
        current_subs=parse_expected_value(value, "currentSubs", expect_int),
        drop_instance_id=parse_expected_value(value, "dropInstanceID", optional_parser(expect_str)),
        is_claimed=parse_expected_value(value, "isClaimed", expect_bool),
    )


def time_based_drop_parser(value: Any):
    expect_dict(value)
    # We only want the name of each benefit, so do a simple parse
    benefits = []
    benefit_edges = parse_expected_value(value, "benefitEdges", list_parser(expect_dict))
    with JsonParentContext("benefitEdges"):
        for index, edge in enumerate(benefit_edges):
            with JsonParentContext(index):
                benefit = parse_expected_value(edge, "benefit", expect_dict)
                with JsonParentContext("benefit"):
                    benefits.append(parse_expected_value(benefit, "name", expect_str))

    return Drops.TimeBasedDrop(
        _id=parse_expected_value(value, "id", expect_str),
        name=parse_expected_value(value, "name", expect_str),
        end_at=parse_expected_value(value, "endAt", expect_iso_8601),
        start_at=parse_expected_value(value, "startAt", expect_iso_8601),
        benefits=benefits,
        required_minutes_watched=parse_expected_value(value, "requiredMinutesWatched", expect_int),
        required_subs=parse_expected_value(value, "requiredSubs", expect_int),
        self_edge=parse_expected_value(value, "self", time_based_drop_self_edge_parser),
    )


def drops_game_parser(value: Any):
    expect_dict(value)
    return Drops.Game(
        _id=parse_expected_value(value, "id", expect_str),
        slug=parse_expected_value(value, "slug", expect_str),
        name=parse_expected_value(value, "name", expect_str),
        box_art_url=parse_value(value, "boxArtURL", optional_parser(expect_str)),
    )


def drop_campaign_parser(value: Any):
    expect_dict(value)
    return Drops.DropCampaign(
        _id=parse_expected_value(value, "id", expect_str),
        status=parse_expected_value(value, "status", expect_str),
        game=parse_expected_value(value, "game", drops_game_parser),
        time_based_drops=parse_expected_value(value, "timeBasedDrops", list_parser(time_based_drop_parser)),
    )


def goal_contribution_parser(value: Any):
    expect_dict(value)
    goal = parse_expected_value(value, "goal", expect_dict)
    with JsonParentContext("goal"):
        goal_id = parse_expected_value(goal, "id", expect_str)

    return ChannelPointsContext.GoalContribution(
        _id=goal_id,
        user_points_contributed_this_stream=parse_expected_value(value, "userPointsContributedThisStream", expect_int),
    )


class Parser:
    def parse_base_response(self, response: Any, expect_no_errors: bool) -> tuple[list[Error], str, dict]:
        """
        Minimal parser for a base GQL response. Gets the `errors` and `data` fields and the `operationName` in
        `extensions`.
        :param response: The response to parse.
        :param expect_no_errors: Whether to expect errors.
        :return: A tuple of a list of any errors, the operation name, and the data dict.
        :raises GQLResponseErrors: If `expect_no_errors` is True and errors were found.
        """
        response_dict = expect_dict(response)
        if response_dict == {}:
            raise InvalidJsonShapeException([], "response was empty")
        errors = parse_value(response_dict, "errors", list_parser(error_parser), [])
        data = parse_value(response_dict, "data", expect_dict)
        extensions = parse_expected_value(response_dict, "extensions", expect_dict)
        operation_name = parse_expected_value(extensions, "operationName", expect_str)
        if expect_no_errors and len(errors) > 0:
            raise GQLResponseErrors(operation_name, errors)
        return errors, operation_name, data

    def parse_video_player_stream_info_overlay_channel_data(self, response: Any):
        """
        Parses responses to VideoPlayerStreamInfoOverlayChannel requests.
        :param response: The response to parse.
        :return: The parsed response.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        errors, operation_name, data = self.parse_base_response(response, True)
        with JsonParentContext("data"):
            return VideoPlayerStreamInfoOverlayChannelResponse(
                user=parse_expected_value(data, "user", user_parser),
            )

    def parse_get_id_from_login_response(self, response: Any):
        """
        Parses responses to GetIDFromLogin requests.
        :param response: The response to parse.
        :return: The parsed response.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        errors, operation_name, data = self.parse_base_response(response, True)
        with JsonParentContext("data"):
            user = parse_expected_value(data, "user", identity)
            return GetIdFromLoginResponse(
                _id=parse_expected_value(user, "id", expect_str)
            )

    def parse_channel_follows_response(self, response: Any):
        """
        Parses responses to ChannelFollows requests.
        :param response: The response to parse.
        :return: The parsed response.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        errors, operation_name, data = self.parse_base_response(response, True)
        with JsonParentContext("data"):
            user = parse_expected_value(data, "user", expect_dict)
            with JsonParentContext("user"):
                # Ignore the user layer, we don't need it right now
                return ChannelFollowsResponse(
                    _id=parse_expected_value(user, "id", expect_str),
                    follows=parse_expected_value(user, "follows", paginated_parser(follow_parser)),
                )

    def parse_join_raid_response(self, response: Any):
        """
        Parses responses to JoinRaid requests.
        :param response: The response to parse.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        self.parse_base_response(response, True)

    def parse_playback_access_token_response(self, response: Any):
        """
        Parses responses to PlaybackAccessToken requests.
        :param response: The response to parse.
        :return: The parsed response.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        errors, operation_name, data = self.parse_base_response(response, True)
        with JsonParentContext("data"):
            # Ignore streamPlaybackAccessToken, it's the only value in data
            stream_playback_access_token = parse_expected_value(data, "streamPlaybackAccessToken", expect_dict)
            with JsonParentContext("streamPlaybackAccessToken"):
                return PlaybackAccessTokenResponse(
                    value=parse_expected_value(stream_playback_access_token, "value", expect_str),
                    signature=parse_expected_value(stream_playback_access_token, "signature", expect_str),
                    authorization=parse_expected_value(
                        stream_playback_access_token, "authorization", authorization_parser
                    )
                )

    def parse_channel_points_context_response(self, response: Any):
        """
        Parses responses to ChannelPointsContext requests.
        :param response: The response to parse.
        :return: The parsed response.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        errors, operation_name, data = self.parse_base_response(response, True)
        with JsonParentContext("data"):
            return ChannelPointsContextResponse(
                community=parse_expected_value(data, "community", optional_parser(community_parser)),
            )

    def parse_make_prediction_response(self, response: Any):
        """
        Parses responses to MakePrediction requests.
        :param response: The response to parse.
        :return: The parsed response.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        errors, operation_name, data = self.parse_base_response(response, True)
        with JsonParentContext("data"):
            make_prediction = parse_expected_value(data, "makePrediction", expect_dict)
            with JsonParentContext("makePrediction"):
                # Ignore makePrediction, it's the only value in data
                return Predictions.MakePredictionResponse(
                    error=parse_expected_value(make_prediction, "error", optional_parser(prediction_error_parser)),
                )

    def parse_claim_community_points_response(self, response: Any):
        """
        Parses responses to ClaimCommunityPoints requests.
        :param response: The response to parse.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        self.parse_base_response(response, True)

    def parse_community_moment_callout_claim_response(self, response: Any):
        """
        Parses responses to CommunityMomentCalloutClaims requests.
        :param response: The response to parse.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        self.parse_base_response(response, True)

    def parse_drops_highlight_service_available_drops(self, response: Any):
        """
        Parses responses to DropsHighlightServiceAvailableDrops requests.
        :param response: The response to parse.
        :return: The parsed response.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        errors, operation_name, data = self.parse_base_response(response, True)
        # We're only interested in the ids
        with JsonParentContext("data"):
            channel = parse_expected_value(data, "channel", expect_dict)
            with JsonParentContext("channel"):
                viewer_drop_campaigns = parse_expected_value(channel, "viewerDropCampaigns", expect_list)
                ids = []
                for index, campaign in enumerate(viewer_drop_campaigns):
                    with JsonParentContext(index):
                        ids.append(parse_expected_value(campaign, "id", expect_str))
                return DropsHighlightServiceAvailableDropsResponse(ids)

    def parse_inventory_response(self, response: Any):
        """
        Parses responses to Inventory requests.
        :param response: The response to parse.
        :return: The parsed response.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        errors, operation_name, data = self.parse_base_response(response, True)
        # We're only interested in the campaigns
        with JsonParentContext("data"):
            return dig(
                data,
                ["currentUser", "inventory"],
                lambda inventory: InventoryResponse(
                    parse_expected_value(
                        inventory,
                        "dropCampaignsInProgress",
                        optional_parser(list_parser(drop_campaign_parser))
                    )
                )
            )

    def parse_viewer_drops_dashboard_response(self, response: Any):
        """
        Parses responses to ViewerDropsDashboard requests.
        :param response: The response to parse.
        :return: The parsed response.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        errors, operation_name, data = self.parse_base_response(response, True)
        with JsonParentContext("data"):
            current_user = parse_expected_value(data, "currentUser", expect_dict)
            with JsonParentContext("currentUser"):
                return Drops.ViewerDropsDashboardResponse(
                    campaigns=parse_expected_value(
                        current_user, "campaigns", optional_parser(list_parser(drop_campaign_parser))
                    ),
                )

    def parse_drop_campaign_details_response(self, response: Any):
        """
        Parses responses to DropCampaignDetails requests.
        :param response: The response to parse.
        :return: The parsed response.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        errors, operation_name, data = self.parse_base_response(response, True)
        # We're only interested in the campaign
        with JsonParentContext("data"):
            user = parse_expected_value(data, "user", expect_dict)
            with JsonParentContext("user"):
                return Drops.DropCampaignDetailsResponse(
                    campaign=parse_expected_value(user, "campaign", drop_campaign_parser),
                )

    def parse_drop_page_claim_drop_rewards(self, response: Any):
        """
        Parses responses to DropPage_ClaimDropRewards requests.
        :param response: The response to parse.
        :return: The parsed response.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        errors, operation_name, data = self.parse_base_response(response, True)
        with JsonParentContext("data"):
            claim_drop_rewards = parse_expected_value(data, "claimDropRewards", expect_dict)
            with JsonParentContext("claimDropRewards"):
                return Drops.DropsPageClaimDropsResponse(
                    status=parse_expected_value(claim_drop_rewards, "status", expect_str),
                )

    def parse_user_points_contribution(self, response: Any):
        """
        Parses responses to UserPointsContribution requests.
        :param response: The response to parse.
        :return: The parsed response.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        errors, operation_name, data = self.parse_base_response(response, True)
        with JsonParentContext("data"):
            return dig(
                data,
                ["user", "channel", "self", "communityPoints"],
                lambda community_points: ChannelPointsContext.UserPointsContributionResponse(
                    goal_contributions=parse_expected_value(
                        community_points,
                        "goalContributions",
                        list_parser(goal_contribution_parser)
                    ),
                )

            )

    def parse_contribute_community_points_community_goal(self, response: Any):
        """
        Parses responses to ContributeCommunityPointsCommunityGoal requests. Doesn't return anything, we're more
        interested in the errors.
        :param response: The response to parse.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        self.parse_base_response(response, True)
