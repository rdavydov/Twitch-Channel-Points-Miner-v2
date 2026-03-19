import copy
import logging
import traceback
from secrets import token_hex
from typing import Callable, Any, Protocol

import requests
from requests import Response

from TwitchChannelPointsMiner.classes.ClientSession import ClientSession
from TwitchChannelPointsMiner.classes.Settings import FollowersOrder
from TwitchChannelPointsMiner.classes.gql.Errors import (
    GQLError,
    RetryError,
    InvalidJsonShapeException,
)
from TwitchChannelPointsMiner.classes.gql.data.Parser import Parser
from TwitchChannelPointsMiner.classes.gql.data.response.ChannelPointsContext import (
    ChannelPointsContextResponse,
    UserPointsContributionResponse,
    ContributeToCommunityGoalResponse,
)
from TwitchChannelPointsMiner.classes.gql.data.response.Drops import (
    DropsHighlightServiceAvailableDropsResponse,
    InventoryResponse,
    ViewerDropsDashboardResponse,
    DropCampaignDetailsResponse,
    DropsPageClaimDropsResponse,
)
from TwitchChannelPointsMiner.classes.gql.data.response.GetIdFromLogin import (
    GetIdFromLoginResponse,
)
from TwitchChannelPointsMiner.classes.gql.data.response.PlaybackAccessToken import (
    PlaybackAccessTokenResponse,
)
from TwitchChannelPointsMiner.classes.gql.data.response.Predictions import (
    MakePredictionResponse,
)
from TwitchChannelPointsMiner.classes.gql.data.response.VideoPlayerStreamInfoOverlayChannel import (
    VideoPlayerStreamInfoOverlayChannelResponse,
)
from TwitchChannelPointsMiner.constants import GQLOperations, CLIENT_ID
from TwitchChannelPointsMiner.utils import create_chunks
from TwitchChannelPointsMiner.utils.AttemptStrategy import (
    SuccessResult,
    ErrorResult,
    AttemptStrategy,
)

logger = logging.getLogger(__name__)


def validate_response(value: Any):
    """
    Validates a parsed response from the GQL API.
    :param value: The response.
    """
    return


def is_recoverable_error(e: Exception) -> bool:
    """
    Returns whether the given exception is recoverable.
    :param e: The exception to check.
    :return: True if the exception is recoverable, False otherwise.
    """
    if isinstance(e, requests.exceptions.RequestException):
        return True
    if isinstance(e, GQLError):
        return e.recoverable()
    return False


def error_context(e: Exception) -> str | None:
    """
    Returns a context string (or None) for the given Error. GQLErrors are well understood and so don't need context,
    anything else is likely a bug and so does need context.
    :param e: The Exception to check.
    :return: The context string, or None if no context is needed.
    """
    if not isinstance(e, GQLError):
        return traceback.format_exc()
    else:
        return None


def parse_list[T](parse: Callable[[Any], T], value: Any) -> list[T]:
    """
    Utility for parsing a list
    :param parse: Parser for the list item type.
    :param value: The value to parse.
    :return:
    """
    if isinstance(value, list):
        return [parse(item) for item in value]
    raise InvalidJsonShapeException([], "list expected")


class PostRequest(Protocol):
    """For creating Type Hints for a function that posts GQL requests."""

    def __call__(
        self, url: str, json: dict | list, headers: dict[str, str]
    ) -> Response: ...


class GQL:
    """
    Integration with Twitch's Graph Query Language (GQL) API.
    """

    def __init__(
        self,
        client_session: ClientSession,
        attempt_strategy: AttemptStrategy | None = None,
        parser: Parser | None = None,
        post_request: PostRequest | None = None,
    ):
        self.client_session = client_session
        """The client session for making requests."""
        self.attempt_strategy = (
            attempt_strategy
            if attempt_strategy is not None
            else AttemptStrategy(attempts=3, attempt_interval_seconds=1)
        )
        """Strategy for handling failed requests."""
        self.parser = Parser() if parser is None else parser
        """The parser for parsing GQL responses."""
        self.post_request = requests.post if post_request is None else post_request
        """Function for posting GQL requests."""

    def __post_gql_request[T](
        self, request_json: dict | list, parse: Callable[[Any], T]
    ) -> T | list[T]:
        response = self.post_request(
            GQLOperations.url,
            json=request_json,
            headers={
                "Authorization": f"OAuth {self.client_session.login.get_auth_token()}",
                "Client-Id": CLIENT_ID,
                "Client-Session-Id": self.client_session.session_id,
                "Client-Version": self.client_session.version,
                "User-Agent": self.client_session.user_agent,
                "X-Device-Id": self.client_session.device_id,
            },
        )
        logger.debug(
            f"Data: {request_json}, Status code: {response.status_code}, Content: {response.text}"
        )
        response.raise_for_status()
        response_json = response.json()
        if isinstance(request_json, list):
            # A batched request should result in a batched response
            if isinstance(response_json, list):
                return list(map(parse, response_json))
            else:
                raise InvalidJsonShapeException(
                    [], f"Expected batched response, got {type(response_json).__name__}"
                )
        else:
            return parse(response_json)

    @staticmethod
    def __handle_result[T](
        result: SuccessResult[T] | ErrorResult, operation_name: str
    ) -> T:
        if isinstance(result, ErrorResult):
            logger.debug(
                f"Unable to make {operation_name} request after {result.attempts} attempts."
            )
            raise RetryError(operation_name, result.errors)
        else:
            if result.attempts > 1:
                logger.debug(
                    f"{operation_name} succeeded after {result.attempts} attempts. Errors: {result.errors}"
                )
            return result.result

    def post_gql_request_single[T](
        self, operation_name: str, request_json: dict, parse: Callable[[Any], T]
    ) -> T:
        """
        Posts the given GQL request. Handles automatic retries according to the `retry_strategy`.
        :param operation_name: The name of the GQL operation.
        :param request_json: The data to send.
        :param parse: The function to use to parse the data.
        :return: The parsed response, either a single object or a list if the request was a list.
        :raises RetryError: If one or more errors occurred while attempting the request.
        """
        result = self.attempt_strategy.make_attempts(
            lambda: self.__post_gql_request(request_json, parse),
            validate_response,
            is_recoverable_error,
            error_context,
        )
        return self.__handle_result(result, operation_name)

    def post_gql_request_batch[T](
        self, operation_name: str, request_json: list[dict], parse: Callable[[Any], T]
    ) -> list[T]:
        """
        Posts the given GQL request batch. Handles automatic retries according to the `retry_strategy`.
        :param operation_name: The name of the GQL operation.
        :param request_json: The data to send as a list of the batched items.
        :param parse: The function to use to parse the data.
        :return: The parsed response, either a single object or a list if the request was a list.
        :raises RetryError: If one or more errors occurred while attempting the request.
        """
        result = self.attempt_strategy.make_attempts(
            lambda: self.__post_gql_request(
                request_json, lambda value: parse_list(parse, value)
            ),
            validate_response,
            is_recoverable_error,
            error_context,
        )
        return self.__handle_result(result, operation_name)

    def video_player_stream_info_overlay_channel(
        self, streamer_username: str
    ) -> VideoPlayerStreamInfoOverlayChannelResponse:
        """
        Gets information about the streamer with the given username.
        :param streamer_username: The username of the streamer.
        :return: The information.
        :raises RetryError: If one or more errors occurred while attempting the request.
        """
        json_data = copy.deepcopy(GQLOperations.VideoPlayerStreamInfoOverlayChannel)
        json_data["variables"] = {"channel": streamer_username}
        return self.post_gql_request_single(
            GQLOperations.VideoPlayerStreamInfoOverlayChannel["operationName"],
            json_data,
            self.parser.parse_video_player_stream_info_overlay_channel_data,
        )

    def get_id_from_login(self, streamer_username: str) -> GetIdFromLoginResponse:
        """
        Gets the user id from a Twitch user's login username.
        :param streamer_username: The username of the user.
        :return: The id or an empty string if the user doesn't exist.
        :raises RetryError: If one or more errors occurred while attempting the request.
        """
        json_data = copy.deepcopy(GQLOperations.GetIDFromLogin)
        json_data["variables"]["login"] = streamer_username
        return self.post_gql_request_single(
            GQLOperations.GetIDFromLogin["operationName"],
            json_data,
            self.parser.parse_get_id_from_login_response,
        )

    def channel_follows(
        self, limit: int = 100, order: FollowersOrder = FollowersOrder.ASC
    ) -> list[str]:
        """
        Gets a list of logins for channels the user follows.
        :param limit: The maximum amount of followers to find per request.
        :param order: The order in which followers should be requested.
        :return: The list of followers, returns none if there was an error.
        :raises RetryError: If one or more errors occurred while attempting the request(s).
        """
        json_data = copy.deepcopy(GQLOperations.ChannelFollows)
        json_data["variables"] = {"limit": limit, "order": str(order)}
        has_next = True
        last_cursor = ""
        follows: list[str] = []
        while has_next is True:
            json_data["variables"]["cursor"] = last_cursor
            parsed_response = self.post_gql_request_single(
                GQLOperations.ChannelFollows["operationName"],
                json_data,
                self.parser.parse_channel_follows_response,
            )
            if parsed_response is not None:
                for edge in parsed_response.follows.edges:
                    follow = edge.node
                    follows.append(follow.login)
                    last_cursor = edge.cursor
                has_next = parsed_response.follows.page_info.has_next_page
            else:
                logger.warning("Unable to get follower list.")
                return []
        return follows

    def join_raid(self, raid_id: str):
        """
        Joins the raid with the given id.
        :param raid_id: The id of the raid to join.
        :raises RetryError: If one or more errors occurred while attempting the request.
        """
        json_data = copy.deepcopy(GQLOperations.JoinRaid)
        json_data["variables"] = {"input": {"raidID": raid_id}}
        self.post_gql_request_single(
            GQLOperations.JoinRaid["operationName"],
            json_data,
            self.parser.parse_join_raid_response,
        )

    def get_playback_access_token(self, username: str) -> PlaybackAccessTokenResponse:
        """
        Gets a playback access token for the streamer with the given username.
        :param username: The username of the streamer.
        :return: The playback access token.
        :raises RetryError: If one or more errors occurred while attempting the request.
        """
        json_data = copy.deepcopy(GQLOperations.PlaybackAccessToken)
        json_data["variables"] = {
            "login": username,
            "isLive": True,
            "isVod": False,
            "vodID": "",
            "playerType": "site",
        }
        return self.post_gql_request_single(
            GQLOperations.PlaybackAccessToken["operationName"],
            json_data,
            self.parser.parse_playback_access_token_response,
        )

    def get_channel_points_context(self, username: str) -> ChannelPointsContextResponse:
        """
        Gets the channel points context for the streamer with the given username.
        :param username: The username of the streamer.
        :return: The channel points context.
        :raises RetryError: If one or more errors occurred while attempting the request.
        """
        json_data = copy.deepcopy(GQLOperations.ChannelPointsContext)
        json_data["variables"] = {"channelLogin": username}
        return self.post_gql_request_single(
            GQLOperations.ChannelPointsContext["operationName"],
            json_data,
            self.parser.parse_channel_points_context_response,
        )

    def make_prediction(
        self, event_id: str, outcome_id: str, points: int
    ) -> MakePredictionResponse:
        """
        Makes a prediction.
        :param event_id: The id of the prediction event.
        :param outcome_id: The id of the outcome on which to predict.
        :param points: The number of points to wager.
        :return: The response.
        :raises RetryError: If one or more errors occurred while attempting the request.
        """
        json_data = copy.deepcopy(GQLOperations.MakePrediction)
        json_data["variables"] = {
            "input": {
                "eventID": event_id,
                "outcomeID": outcome_id,
                "points": points,
                "transactionID": token_hex(16),
            }
        }
        return self.post_gql_request_single(
            GQLOperations.MakePrediction["operationName"],
            json_data,
            self.parser.parse_make_prediction_response,
        )

    def claim_community_points(self, channel_id: str, claim_id: str):
        """
        Claims the community points claim with the given id for the given channel.
        :param channel_id: The id of the channel of the claim.
        :param claim_id: The id of the claim.
        :raises RetryError: If one or more errors occurred while attempting the request.
        """
        json_data = copy.deepcopy(GQLOperations.ClaimCommunityPoints)
        json_data["variables"] = {
            "input": {"channelID": channel_id, "claimID": claim_id}
        }
        self.post_gql_request_single(
            GQLOperations.ClaimCommunityPoints["operationName"],
            json_data,
            self.parser.parse_claim_community_points_response,
        )

    def claim_moment(self, moment_id: str):
        """
        Claims the moment of the given id.
        :param moment_id: The id of the moment to claim.
        :raises RetryError: If one or more errors occurred while attempting the request.
        """
        json_data = copy.deepcopy(GQLOperations.CommunityMomentCallout_Claim)
        json_data["variables"] = {"input": {"momentID": moment_id}}
        self.post_gql_request_single(
            GQLOperations.CommunityMomentCallout_Claim["operationName"],
            json_data,
            self.parser.parse_community_moment_callout_claim_response,
        )

    def get_available_drops(
        self, channel_id: str
    ) -> DropsHighlightServiceAvailableDropsResponse:
        """
        Gets the ids of all drops that are available.
        :param channel_id: The id of the channel to check.
        :return: The response.
        :raises RetryError: If one or more errors occurred while attempting the request.
        """
        json_data = copy.deepcopy(GQLOperations.DropsHighlightService_AvailableDrops)
        json_data["variables"] = {"channelID": channel_id}
        return self.post_gql_request_single(
            GQLOperations.DropsHighlightService_AvailableDrops["operationName"],
            json_data,
            self.parser.parse_drops_highlight_service_available_drops,
        )

    def get_inventory(self) -> InventoryResponse:
        """
        Gets the user's Inventory.
        :return: The response.
        :raises RetryError: If one or more errors occurred while attempting the request.
        """
        return self.post_gql_request_single(
            GQLOperations.Inventory["operationName"],
            GQLOperations.Inventory,
            self.parser.parse_inventory_response,
        )

    def get_viewer_drops_dashboard(self) -> ViewerDropsDashboardResponse:
        """
        Gets the viewer drops dashboard.
        :return: The response.
        :raises RetryError: If one or more errors occurred while attempting the request.
        """
        return self.post_gql_request_single(
            GQLOperations.ViewerDropsDashboard["operationName"],
            GQLOperations.ViewerDropsDashboard,
            self.parser.parse_viewer_drops_dashboard_response,
        )

    def get_drop_campaign_details(
        self, campaign_ids: list[str]
    ) -> list[DropCampaignDetailsResponse]:
        """
        Gets the drop campaign details for the campaigns with the given ids.
        :param campaign_ids: The ids of the campaigns.
        :return: The response.
        :raises RetryError: If one or more errors occurred while attempting the request(s).
        """
        result = []
        # Batch the requests into chunks of 20
        chunks = create_chunks(campaign_ids, 20)
        for chunk in chunks:
            json_data = []
            for campaign in chunk:
                json_data.append(copy.deepcopy(GQLOperations.DropCampaignDetails))
                json_data[-1]["variables"] = {
                    "dropID": campaign,
                    "channelLogin": f"{self.client_session.login.get_user_id()}",
                }

            response = self.post_gql_request_batch(
                GQLOperations.DropCampaignDetails["operationName"],
                json_data,
                self.parser.parse_drop_campaign_details_response,
            )

            if not isinstance(response, list):
                logger.debug("Unexpected campaigns response format, skipping chunk")
                continue
            for item in response:
                if item is not None:
                    result.append(item)
        return result

    def claim_drop_rewards(self, drop_instance_id: str) -> DropsPageClaimDropsResponse:
        """
        Claims the rewards for the drop with the given id.
        :param drop_instance_id: The id of the drop.
        :return: The response.
        :raises RetryError: If one or more errors occurred while attempting the request.
        """
        json_data = copy.deepcopy(GQLOperations.DropsPage_ClaimDropRewards)
        json_data["variables"] = {"input": {"dropInstanceID": drop_instance_id}}
        return self.post_gql_request_single(
            GQLOperations.DropsPage_ClaimDropRewards["operationName"],
            json_data,
            self.parser.parse_drop_page_claim_drop_rewards,
        )

    def get_user_points_contribution(
        self, username: str
    ) -> UserPointsContributionResponse:
        """
        Gets the user points contribution for streamer with the given username.
        :param username: The username of the streamer.
        :return: The response.
        :raises RetryError: If one or more errors occurred while attempting the request.
        """
        json_data = copy.deepcopy(GQLOperations.UserPointsContribution)
        json_data["variables"] = {"channelLogin": username}
        return self.post_gql_request_single(
            GQLOperations.UserPointsContribution["operationName"],
            json_data,
            self.parser.parse_user_points_contribution,
        )

    def contribute_to_community_goal(
        self, channel_id, goal_id, amount
    ) -> ContributeToCommunityGoalResponse:
        """
        Contributes the given amount of channel points to the given community goal.
        :param channel_id: The id of the channel running the goal.
        :param goal_id: The id of the goal.
        :param amount: The amount to contribute.
        :raises RetryError: If one or more errors occurred while attempting the request.
        """
        json_data = copy.deepcopy(GQLOperations.ContributeCommunityPointsCommunityGoal)
        json_data["variables"] = {
            "input": {
                "amount": amount,
                "channelID": channel_id,
                "goalID": goal_id,
                "transactionID": token_hex(16),
            }
        }
        return self.post_gql_request_single(
            GQLOperations.ContributeCommunityPointsCommunityGoal["operationName"],
            json_data,
            self.parser.parse_contribute_community_points_community_goal,
        )


class GQLFactory:
    """Factory class for creating GQL objects."""

    def __init__(
        self,
        attempt_strategy: AttemptStrategy | None = None,
        parser: Parser | None = None,
        post_request: PostRequest | None = None,
    ):
        self.attempt_strategy = attempt_strategy
        self.parser = parser
        self.post_request = post_request

    def create(self, client_session: ClientSession) -> GQL:
        """
        Creates a new GQL instance.
        :param client_session: The ClientSession for the instance.
        :return: The instance.
        """
        return GQL(
            client_session, self.attempt_strategy, self.parser, self.post_request
        )
