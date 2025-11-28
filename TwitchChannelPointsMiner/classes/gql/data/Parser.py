import datetime
from typing import Callable, Any, ContextManager

from TwitchChannelPointsMiner.classes.gql.Errors import (
    InvalidJsonShapeException,
    GQLResponseErrors,
)
from TwitchChannelPointsMiner.classes.gql.data.response import (
    ChannelPointsContext,
    Predictions,
    Drops,
    PlaybackAccessToken,
)
from TwitchChannelPointsMiner.classes.gql.data.response.BroadcastSettings import (
    BroadcastSettings,
    GameBroadcastSettings,
)
from TwitchChannelPointsMiner.classes.gql.data.response.ChannelFollows import (
    ChannelFollowsResponse,
    Follow,
)
from TwitchChannelPointsMiner.classes.gql.data.response.ChannelPointsContext import (
    ChannelPointsContextResponse,
    ContributeToCommunityGoalResponse,
)
from TwitchChannelPointsMiner.classes.gql.data.response.Drops import (
    DropsHighlightServiceAvailableDropsResponse,
    InventoryResponse,
)
from TwitchChannelPointsMiner.classes.gql.data.response.Error import Error
from TwitchChannelPointsMiner.classes.gql.data.response.GetIdFromLogin import (
    GetIdFromLoginResponse,
)
from TwitchChannelPointsMiner.classes.gql.data.response.Pagination import (
    PageInfo,
    Paginated,
    Edge,
)
from TwitchChannelPointsMiner.classes.gql.data.response.PlaybackAccessToken import (
    PlaybackAccessTokenResponse,
)
from TwitchChannelPointsMiner.classes.gql.data.response.Stream import Stream, Tag
from TwitchChannelPointsMiner.classes.gql.data.response.VideoPlayerStreamInfoOverlayChannel import (
    User,
    VideoPlayerStreamInfoOverlayChannelResponse,
)


class JsonParentContext(ContextManager):
    """Context Manager that appends the parent name to InvalidJsonShapeExceptions"""

    def __init__(self, name: str | int):
        self.name = name

    def __exit__(self, exc_type, exc_val, exc_tb):
        if isinstance(exc_val, InvalidJsonShapeException):
            exc_val.path.append(self.name)


def expect_dict(value: Any) -> dict:
    """
    Parser that checks that the value is a dict then returns it.
    :raises InvalidJsonShapeException: if the value is not a dict
    """
    if not isinstance(value, dict):
        raise InvalidJsonShapeException([], "dict expected")
    return value


def expect_list(value: Any) -> list:
    """
    Parser that checks that the value is a list then returns it.
    :raises InvalidJsonShapeException: if the value is not a list.
    """
    if not isinstance(value, list):
        raise InvalidJsonShapeException([], "list expected")
    return value


def expect_str(value: Any) -> str:
    """
    Parser that checks that the value is a string then returns it.
    :raises InvalidJsonShapeException: if the value is not a string.
    """
    if not isinstance(value, str):
        raise InvalidJsonShapeException([], "str expected")
    return value


def expect_int(value: Any) -> int:
    """
    Parser that checks that the value is an int then returns it.
    :raises InvalidJsonShapeException: if the value is not an int.
    """
    if not isinstance(value, int):
        raise InvalidJsonShapeException([], "int expected")
    return value


def expect_bool(value: Any) -> bool:
    """
    Parser that checks that the value is a bool then returns it.
    :raises InvalidJsonShapeException: if the value is not a bool.
    """
    if not isinstance(value, bool):
        raise InvalidJsonShapeException([], "bool expected")
    return value


def expect_iso_8601(value: Any) -> datetime.datetime:
    """
    Parser that checks that the value is a valid ISO8601 string and returns it as a datetime.
    :raises InvalidJsonShapeException: if the value is not a valid ISO8601 string.
    """
    if not isinstance(value, str):
        raise InvalidJsonShapeException([], "str expected")

    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise InvalidJsonShapeException([], f"time data '{value}' does not match format")


def parse_expected_value[T](
    source: dict, property_name: str, type_parser: Callable[[Any], T]
) -> T:
    """
    Parses a value, with the given property name, in the given dict, and parses it using the given parser.
    :param source: The parent object, containing the value to parse.
    :param property_name: The property name of the value to parse.
    :param type_parser: A parser for the type of the value.
    :return: The parsed value.
    :raises InvalidJsonShapeException: if the property is not in the dict or the value cannot be parsed.
    """
    if property_name not in source:
        raise InvalidJsonShapeException([property_name], "value should not be None")
    with JsonParentContext(property_name):
        return type_parser(source[property_name])


def parse_value[T](
    source: dict,
    property_name: str,
    type_parser: Callable[[Any], T],
    default: T | None = None,
) -> T | None:
    """
    Parses a value, with the given property name, in the given dict, and parses it using the given parser. The property
    may not exist in the source, in which case we return the default value.
    :param source: The parent object, containing the value to parse.
    :param property_name: The property name of the value to parse.
    :param type_parser: A parser for the type of the value.
    :param default: The default value to return if the value cannot be found (defaults to None).
    :return: The parsed value or the default if the property cannot be found.
    """
    if property_name not in source:
        return default
    with JsonParentContext(property_name):
        return type_parser(source[property_name])


def list_parser[T](value_type_parser: Callable[[Any], T]) -> Callable[[Any], list[T]]:
    """
    Returns a parser function that parses a value as a list and each item in the list using the given parser.
    :param value_type_parser: The parser for each value in the list.
    :return: The list parser function.
    """

    def inner_parser(source: Any) -> list[T]:
        expect_list(source)

        for index, item in enumerate(source):
            with JsonParentContext(index):
                source[index] = value_type_parser(item)
        return source

    return inner_parser


def optional_parser[T](
    value_type_parser: Callable[[Any], T],
) -> Callable[[Any], T | None]:
    """
    Returns a parser function that parses a value as either None or using the given parser.
    :param value_type_parser: The parser for the type of the value.
    :return: The parser function.
    """

    def inner_parser(value: Any) -> T | None:
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


# Parsers for GQL response types


def error_parser(value: Any) -> Error:
    expect_dict(value)
    message = parse_expected_value(value, "message", expect_str)
    recoverable = message in ["service timeout"]
    return Error(
        recoverable, message, parse_value(value, "path", list_parser(expect_str))
    )


def page_info_parser(value: Any) -> PageInfo:
    return PageInfo(
        has_next_page=parse_expected_value(value, "hasNextPage", expect_bool),
        start_cursor=parse_value(value, "startCursor", expect_str),
        end_cursor=parse_value(value, "endCursor", expect_str),
    )


def paginated_parser[T](
    value_parser: Callable[[Any], T],
) -> Callable[[Any], Paginated[T]]:
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
        localized_name=parse_expected_value(value, "localizedName", expect_str),
    )


def game_parser(value: Any) -> GameBroadcastSettings:
    expect_dict(value)
    return GameBroadcastSettings(
        _id=parse_expected_value(value, "id", expect_str),
        display_name=parse_expected_value(value, "displayName", expect_str),
        name=parse_expected_value(value, "name", expect_str),
    )


def broadcast_settings_parser(value: Any) -> BroadcastSettings:
    expect_dict(value)
    return BroadcastSettings(
        _id=parse_expected_value(value, "id", expect_str),
        title=parse_expected_value(value, "title", expect_str),
        game=parse_expected_value(value, "game", optional_parser(game_parser)),
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
    broadcast_settings = parse_expected_value(
        value, "broadcastSettings", broadcast_settings_parser
    )
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
        disable_notifications=parse_expected_value(
            value, "disableNotifications", expect_bool
        ),
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
        banner_image_url=parse_expected_value(
            value, "bannerImageURL", optional_parser(expect_str)
        ),
        display_name=parse_expected_value(value, "displayName", expect_str),
        login=parse_expected_value(value, "login", expect_str),
        profile_image_url=parse_expected_value(value, "profileImageURL", expect_str),
        _self=parse_expected_value(value, "self", follow_self_edge_parser),
    )


def authorization_parser(value: Any) -> PlaybackAccessToken.Authorization:
    expect_dict(value)
    return PlaybackAccessToken.Authorization(
        is_forbidden=parse_expected_value(value, "isForbidden", expect_bool),
        forbidden_reason_code=parse_expected_value(
            value, "forbiddenReasonCode", expect_str
        ),
    )


def claim_parser(value: Any) -> ChannelPointsContext.Properties.Claim:
    expect_dict(value)
    return ChannelPointsContext.Properties.Claim(
        _id=parse_expected_value(value, "id", expect_str),
    )


def multiplier_parser(value: Any) -> ChannelPointsContext.Properties.Multiplier:
    expect_dict(value)
    return ChannelPointsContext.Properties.Multiplier(
        factor=parse_expected_value(value, "factor", float),
    )


def community_points_parser(value: Any) -> ChannelPointsContext.Properties:
    expect_dict(value)
    return ChannelPointsContext.Properties(
        available_claim=parse_expected_value(
            value, "availableClaim", optional_parser(claim_parser)
        ),
        balance=parse_expected_value(value, "balance", expect_int),
        active_multipliers=parse_expected_value(
            value, "activeMultipliers", list_parser(multiplier_parser)
        ),
    )


def channel_self_edge_parser(
    value: Any,
) -> ChannelPointsContext.Channel.ChannelSelfEdge:
    expect_dict(value)
    return ChannelPointsContext.Channel.ChannelSelfEdge(
        community_points=parse_expected_value(
            value, "communityPoints", community_points_parser
        ),
    )


def community_goal_parser(value: Any) -> ChannelPointsContext.CommunityGoal:
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


def community_points_settings_parser(
    value: Any,
) -> ChannelPointsContext.CommunityPointsSettings:
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
            value, "communityPointsSettings", community_points_settings_parser
        ),
    )


def community_parser(value: Any) -> ChannelPointsContext.CommunityUser:
    expect_dict(value)
    return ChannelPointsContext.CommunityUser(
        _id=parse_expected_value(value, "id", expect_str),
        display_name=parse_expected_value(value, "displayName", expect_str),
        channel=parse_expected_value(value, "channel", channel_parser),
    )


def prediction_error_parser(value: Any) -> Predictions.Error:
    expect_dict(value)
    return Predictions.Error(
        code=parse_expected_value(value, "code", expect_str),
    )


def time_based_drop_self_edge_parser(
    value: Any,
) -> Drops.TimeBasedDropInProgress.SelfEdge:
    expect_dict(value)
    return Drops.TimeBasedDropInProgress.SelfEdge(
        has_preconditions_met=parse_expected_value(
            value, "hasPreconditionsMet", expect_bool
        ),
        current_minutes_watched=parse_expected_value(
            value, "currentMinutesWatched", expect_int
        ),
        current_subs=parse_expected_value(value, "currentSubs", expect_int),
        drop_instance_id=parse_expected_value(
            value, "dropInstanceID", optional_parser(expect_str)
        ),
        is_claimed=parse_expected_value(value, "isClaimed", expect_bool),
    )


def drop_benefits_parser(value: Any) -> list[str]:
    expect_list(value)
    benefits = []
    for index, edge in enumerate(value):
        with JsonParentContext(index):
            benefit = parse_expected_value(edge, "benefit", expect_dict)
            with JsonParentContext("benefit"):
                benefits.append(parse_expected_value(benefit, "name", expect_str))
    return benefits


def time_based_drop_details_parser(value: Any) -> Drops.TimeBasedDropDetails:
    expect_dict(value)
    return Drops.TimeBasedDropDetails(
        _id=parse_expected_value(value, "id", expect_str),
        name=parse_expected_value(value, "name", expect_str),
        end_at=parse_expected_value(value, "endAt", expect_iso_8601),
        start_at=parse_expected_value(value, "startAt", expect_iso_8601),
        benefits=parse_expected_value(value, "benefitEdges", drop_benefits_parser),
        required_minutes_watched=parse_expected_value(
            value, "requiredMinutesWatched", expect_int
        ),
        required_subs=parse_expected_value(value, "requiredSubs", expect_int),
    )


def drop_campaign_dashboard_parser(value: Any) -> Drops.DropCampaignDashboard:
    expect_dict(value)
    return Drops.DropCampaignDashboard(
        _id=parse_expected_value(value, "id", expect_str),
        status=parse_expected_value(value, "status", expect_str),
    )


def drops_game_details_parser(value: Any) -> Drops.GameDetails:
    expect_dict(value)
    return Drops.GameDetails(
        _id=parse_expected_value(value, "id", expect_str),
        slug=parse_expected_value(value, "slug", expect_str),
        display_name=parse_expected_value(value, "displayName", expect_str),
    )


def time_based_drop_in_progress_parser(value: Any) -> Drops.TimeBasedDropInProgress:
    expect_dict(value)
    return Drops.TimeBasedDropInProgress(
        _id=parse_expected_value(value, "id", expect_str),
        name=parse_expected_value(value, "name", expect_str),
        end_at=parse_expected_value(value, "endAt", expect_iso_8601),
        start_at=parse_expected_value(value, "startAt", expect_iso_8601),
        benefits=parse_expected_value(value, "benefitEdges", drop_benefits_parser),
        required_minutes_watched=parse_expected_value(
            value, "requiredMinutesWatched", expect_int
        ),
        required_subs=parse_expected_value(value, "requiredSubs", expect_int),
        self_edge=parse_expected_value(value, "self", time_based_drop_self_edge_parser),
    )


def drop_campaign_in_progress_parser(value: Any) -> Drops.DropCampaignInProgress:
    expect_dict(value)
    return Drops.DropCampaignInProgress(
        _id=parse_expected_value(value, "id", expect_str),
        time_based_drops=parse_expected_value(
            value, "timeBasedDrops", list_parser(time_based_drop_in_progress_parser)
        ),
    )


def drop_campaign_details_parser(value: Any) -> Drops.DropCampaignDetails:
    expect_dict(value)
    allow = parse_expected_value(value, "allow", expect_dict)
    # We only want the ids of allow channels, if they exist
    allow_channel_ids: list[str] | None = None
    with JsonParentContext("allow"):
        channels = parse_expected_value(allow, "channels", optional_parser(expect_list))
        if channels is not None:
            allow_channel_ids = []
            with JsonParentContext("channels"):
                for index, channel in enumerate(channels):
                    with JsonParentContext(index):
                        allow_channel_ids.append(
                            parse_expected_value(channel, "id", expect_str)
                        )
    return Drops.DropCampaignDetails(
        _id=parse_expected_value(value, "id", expect_str),
        name=parse_expected_value(value, "name", expect_str),
        status=parse_expected_value(value, "status", expect_str),
        game=parse_expected_value(value, "game", drops_game_details_parser),
        allow_channel_ids=allow_channel_ids,
        time_based_drops=parse_expected_value(
            value, "timeBasedDrops", list_parser(time_based_drop_details_parser)
        ),
    )


def goal_contribution_parser(value: Any) -> ChannelPointsContext.GoalContribution:
    expect_dict(value)
    goal = parse_expected_value(value, "goal", expect_dict)
    with JsonParentContext("goal"):
        goal_id = parse_expected_value(goal, "id", expect_str)

    return ChannelPointsContext.GoalContribution(
        _id=goal_id,
        user_points_contributed_this_stream=parse_expected_value(
            value, "userPointsContributedThisStream", expect_int
        ),
    )


class Parser:
    """Class that can parse responses from the Twitch GQL API."""

    def parse_base_response(
        self, response: Any, expect_no_errors: bool
    ) -> tuple[list[Error], str, dict]:
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
        if expect_no_errors and errors is not None and len(errors) > 0:
            raise GQLResponseErrors(operation_name, errors)
        return errors or [], operation_name, data or {}

    def parse_video_player_stream_info_overlay_channel_data(self, response: Any):
        """
        Parses responses to VideoPlayerStreamInfoOverlayChannel requests.
        :param response: The response to parse.
        :return: The parsed response.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        _, _, data = self.parse_base_response(response, True)
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
        _, _, data = self.parse_base_response(response, True)
        with JsonParentContext("data"):
            user = parse_expected_value(data, "user", expect_dict)
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
        _, _, data = self.parse_base_response(response, True)
        with JsonParentContext("data"):
            user = parse_expected_value(data, "user", expect_dict)
            with JsonParentContext("user"):
                # Ignore the user layer, we don't need it right now
                return ChannelFollowsResponse(
                    _id=parse_expected_value(user, "id", expect_str),
                    follows=parse_expected_value(
                        user, "follows", paginated_parser(follow_parser)
                    ),
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
        _, _, data = self.parse_base_response(response, True)
        with JsonParentContext("data"):
            # Ignore streamPlaybackAccessToken, it's the only value in data
            stream_playback_access_token = parse_expected_value(
                data, "streamPlaybackAccessToken", expect_dict
            )
            with JsonParentContext("streamPlaybackAccessToken"):
                return PlaybackAccessTokenResponse(
                    value=parse_expected_value(
                        stream_playback_access_token, "value", expect_str
                    ),
                    signature=parse_expected_value(
                        stream_playback_access_token, "signature", expect_str
                    ),
                    authorization=parse_expected_value(
                        stream_playback_access_token,
                        "authorization",
                        authorization_parser,
                    ),
                )

    def parse_channel_points_context_response(self, response: Any):
        """
        Parses responses to ChannelPointsContext requests.
        :param response: The response to parse.
        :return: The parsed response.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        _, _, data = self.parse_base_response(response, True)
        with JsonParentContext("data"):
            return ChannelPointsContextResponse(
                community=parse_expected_value(
                    data, "community", optional_parser(community_parser)
                ),
            )

    def parse_make_prediction_response(self, response: Any):
        """
        Parses responses to MakePrediction requests.
        :param response: The response to parse.
        :return: The parsed response.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        _, _, data = self.parse_base_response(response, True)
        with JsonParentContext("data"):
            make_prediction = parse_expected_value(data, "makePrediction", expect_dict)
            with JsonParentContext("makePrediction"):
                # Ignore makePrediction, it's the only value in data
                return Predictions.MakePredictionResponse(
                    error=parse_expected_value(
                        make_prediction,
                        "error",
                        optional_parser(prediction_error_parser),
                    ),
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
        _, _, data = self.parse_base_response(response, True)
        # We're only interested in the ids
        with JsonParentContext("data"):
            channel = parse_expected_value(data, "channel", expect_dict)
            with JsonParentContext("channel"):
                viewer_drop_campaigns = parse_expected_value(
                    channel, "viewerDropCampaigns", optional_parser(expect_list)
                )
                ids = []
                if viewer_drop_campaigns is not None:
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
        _, _, data = self.parse_base_response(response, True)
        # We're only interested in the campaigns
        with JsonParentContext("data"):
            return dig(
                data,
                ["currentUser", "inventory"],
                lambda inventory: InventoryResponse(
                    parse_expected_value(
                        inventory,
                        "dropCampaignsInProgress",
                        optional_parser(list_parser(drop_campaign_in_progress_parser)),
                    )
                ),
            )

    def parse_viewer_drops_dashboard_response(self, response: Any):
        """
        Parses responses to ViewerDropsDashboard requests.
        :param response: The response to parse.
        :return: The parsed response.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        _, _, data = self.parse_base_response(response, True)
        with JsonParentContext("data"):
            current_user = parse_expected_value(data, "currentUser", expect_dict)
            with JsonParentContext("currentUser"):
                return Drops.ViewerDropsDashboardResponse(
                    campaigns=parse_expected_value(
                        current_user,
                        "dropCampaigns",
                        optional_parser(list_parser(drop_campaign_dashboard_parser)),
                    ),
                )

    def parse_drop_campaign_details_response(self, response: Any):
        """
        Parses responses to DropCampaignDetails requests.
        :param response: The response to parse.
        :return: The parsed response.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        _, _, data = self.parse_base_response(response, True)
        # We're only interested in the campaign
        with JsonParentContext("data"):
            user = parse_expected_value(data, "user", expect_dict)
            with JsonParentContext("user"):
                return Drops.DropCampaignDetailsResponse(
                    campaign=parse_expected_value(
                        user, "campaign", drop_campaign_details_parser
                    ),
                )

    def parse_drop_page_claim_drop_rewards(self, response: Any):
        """
        Parses responses to DropPage_ClaimDropRewards requests.
        :param response: The response to parse.
        :return: The parsed response.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        _, _, data = self.parse_base_response(response, True)
        status = None
        with JsonParentContext("data"):
            claim_drop_rewards = parse_expected_value(
                data, "claimDropRewards", optional_parser(expect_dict)
            )
            # Apparently this can be None but I couldn't find a case where it was
            if claim_drop_rewards is not None:
                with JsonParentContext("claimDropRewards"):
                    status = parse_expected_value(
                        claim_drop_rewards, "status", expect_str
                    )

            data_errors = parse_value(data, "errors", optional_parser(expect_list))
            return Drops.DropsPageClaimDropsResponse(status, data_errors)

    def parse_user_points_contribution(
        self, response: Any
    ) -> ChannelPointsContext.UserPointsContributionResponse:
        """
        Parses responses to UserPointsContribution requests.
        :param response: The response to parse.
        :return: The parsed response.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        _, _, data = self.parse_base_response(response, True)
        with JsonParentContext("data"):
            return dig(
                data,
                ["user", "channel", "self", "communityPoints"],
                lambda community_points: ChannelPointsContext.UserPointsContributionResponse(
                    goal_contributions=parse_expected_value(
                        community_points,
                        "goalContributions",
                        list_parser(goal_contribution_parser),
                    ),
                ),
            )

    def parse_contribute_community_points_community_goal(
        self, response: Any
    ) -> ContributeToCommunityGoalResponse:
        """
        Parses responses to ContributeCommunityPointsCommunityGoal requests. Doesn't return anything, we're more
        interested in the errors.
        :param response: The response to parse.
        :raises: GQLError: If the response contains errors or there is an issue parsing the response.
        """
        _, _, data = self.parse_base_response(response, True)
        with JsonParentContext("data"):
            contribute = parse_expected_value(
                data, "contributeCommunityPointsCommunityGoal", expect_dict
            )
            with JsonParentContext("contributeCommunityPointsCommunityGoal"):
                return ContributeToCommunityGoalResponse(
                    error=parse_expected_value(
                        contribute, "error", optional_parser(expect_str)
                    ),
                )
