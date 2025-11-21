import copy
import logging
from secrets import token_hex
from typing import Callable, Any

import requests

from TwitchChannelPointsMiner.classes.ClientSession import ClientSession
from TwitchChannelPointsMiner.classes.Settings import FollowersOrder
from TwitchChannelPointsMiner.classes.gql.data.Parser import Parser, GQLError
from TwitchChannelPointsMiner.classes.gql.data.response.ChannelPointsContext import (
    ChannelPointsContextResponse,
    UserPointsContributionResponse
)
from TwitchChannelPointsMiner.classes.gql.data.response.Drops import (
    DropsHighlightServiceAvailableDropsResponse,
    InventoryResponse, ViewerDropsDashboardResponse, DropCampaignDetailsResponse, DropsPageClaimDropsResponse
)
from TwitchChannelPointsMiner.classes.gql.data.response.GetIdFromLogin import GetIdFromLoginResponse
from TwitchChannelPointsMiner.classes.gql.data.response.PlaybackAccessToken import PlaybackAccessTokenResponse
from TwitchChannelPointsMiner.classes.gql.data.response.Predictions import MakePredictionResponse
from TwitchChannelPointsMiner.classes.gql.data.response.VideoPlayerStreamInfoOverlayChannel import \
    VideoPlayerStreamInfoOverlayChannelResponse
from TwitchChannelPointsMiner.constants import GQLOperations, CLIENT_ID
from TwitchChannelPointsMiner.utils import create_chunks

logger = logging.getLogger(__name__)


class GQL:
    """
    Integration with Twitch's Graph Query Language (GQL) API.
    """

    def __init__(self, parser: Parser, client_session: ClientSession, retries: int = 3):
        self.parser = parser
        """The parser for parsing GQL responses."""
        self.client_session = client_session
        """The client session for making requests."""
        self.retries = retries
        """The number of times to retry a recoverable request."""

    def post_gql_request[T](self, json_data: dict | list, parse: Callable[[Any], T]) -> T | None:
        """
        Posts the given GQL request.
        :param json_data: The data to send, can be either a dict or a list if sending multiple request operations.
        :param parse: The function to use to parse the data.
        :return: The response json.
        """
        attempts = 0
        while attempts < self.retries:
            attempts += 1
            try:
                response = requests.post(
                    GQLOperations.url,
                    json=json_data,
                    headers={
                        "Authorization": f"OAuth {self.client_session.login.get_auth_token()}",
                        "Client-Id": CLIENT_ID,
                        "Client-Session-Id": self.client_session.session_id,
                        "Client-Version": self.client_session.client_version,
                        "User-Agent": self.client_session.user_agent,
                        "X-Device-Id": self.client_session.device_id,
                    },
                )
                logger.debug(f"Data: {json_data}, Status code: {response.status_code}, Content: {response.text}")
                return parse(response.json())
            except (requests.exceptions.RequestException, GQLError) as e:
                if attempts == self.retries:
                    logger.error(f"Error handling GQL response.", e)
                    return None
        logger.error(f"Unable to make request after {attempts} attempts.")
        return None

    def video_player_stream_info_overlay_channel(
        self, streamer_username: str
    ) -> VideoPlayerStreamInfoOverlayChannelResponse | None:
        json_data = copy.deepcopy(
            GQLOperations.VideoPlayerStreamInfoOverlayChannel
        )
        json_data["variables"] = {"channel": streamer_username}
        return self.post_gql_request(json_data, self.parser.parse_video_player_stream_info_overlay_channel_data)

    def get_id_from_login(self, streamer_username: str) -> GetIdFromLoginResponse | None:
        """
        Gets the user id from a Twitch user's login username.
        :param streamer_username: The username of the user.
        :return: The id or an empty string if the user doesn't exist.
        """
        json_data = copy.deepcopy(GQLOperations.GetIDFromLogin)
        json_data["variables"]["login"] = streamer_username
        return self.post_gql_request(json_data, self.parser.parse_get_id_from_login_response)

    def channel_follows(
        self, limit: int = 100, order: FollowersOrder = FollowersOrder.ASC
    ) -> list[str]:
        """
        Gets a list of logins for channels the user follows.
        :param limit: The maximum amount of followers to find per request.
        :param order: The order in which followers should be requested.
        :return: The list of followers, returns none if there was an error.
        """
        json_data = copy.deepcopy(GQLOperations.ChannelFollows)
        json_data["variables"] = {"limit": limit, "order": str(order)}
        has_next = True
        last_cursor = ""
        follows: list[str] = []
        while has_next is True:
            json_data["variables"]["cursor"] = last_cursor
            parsed_response = self.post_gql_request(json_data, self.parser.parse_channel_follows_response)
            if parsed_response is not None:
                for follow in parsed_response.follows:
                    follows.append(follow.login)
                    last_cursor = follow.cursor
                has_next = parsed_response.follows.pageInfo.has_next
            else:
                logger.warning("Unable to get follower list.")
                return []
        return follows

    def join_raid(self, raid_id: str):
        """
        Joins the raid with the given id.
        :param raid_id: The id of the raid to join.
        :raises: GQLError: If the raid couldn't be joined.
        """
        json_data = copy.deepcopy(GQLOperations.JoinRaid)
        json_data["variables"] = {"input": {"raidID": raid_id}}
        self.post_gql_request(json_data, self.parser.parse_join_raid_response)

    def get_playback_access_token(self, username: str) -> PlaybackAccessTokenResponse | None:
        """
        Gets a playback access token for the streamer with the given username.
        :param username: The username of the streamer.
        :return: The playback access token.
        """
        json_data = copy.deepcopy(GQLOperations.PlaybackAccessToken)
        json_data["variables"] = {
            "login": username,
            "isLive": True,
            "isVod": False,
            "vodID": "",
            "playerType": "site"
            # "playerType": "picture-by-picture",
        }
        return self.post_gql_request(json_data, self.parser.parse_playback_access_token_response)

    def get_channel_points_context(self, username: str) -> ChannelPointsContextResponse | None:
        """
        Gets the channel points context for the streamer with the given username.
        :param username: The username of the streamer.
        :return: The channel points context.
        """
        json_data = copy.deepcopy(GQLOperations.ChannelPointsContext)
        json_data["variables"] = {"channelLogin": username}

        return self.post_gql_request(json_data, self.parser.parse_channel_points_context_response)

    def make_prediction(self, event_id: str, outcome_id: str, points: int) -> MakePredictionResponse | None:
        """
        Makes a prediction.
        :param event_id: The id of the prediction event.
        :param outcome_id: The id of the outcome on which to predict.
        :param points: The number of points to wager.
        :return: The response.
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
        return self.post_gql_request(json_data, self.parser.parse_make_prediction_response)

    def claim_community_points(self, channel_id: str, claim_id: str):
        """
        Claims the community points claim with the given id for the given channel.
        :param channel_id: The id of the channel of the claim.
        :param claim_id: The id of the claim.
        """
        json_data = copy.deepcopy(GQLOperations.ClaimCommunityPoints)
        json_data["variables"] = {
            "input": {"channelID": channel_id, "claimID": claim_id}
        }
        self.post_gql_request(json_data, self.parser.parse_claim_community_points_response)

    def claim_moment(self, moment_id: str):
        """
        Claims the moment of the given id.
        :param moment_id: The id of the moment to claim.
        """
        json_data = copy.deepcopy(GQLOperations.CommunityMomentCallout_Claim)
        json_data["variables"] = {"input": {"momentID": moment_id}}
        self.post_gql_request(json_data, self.parser.parse_community_moment_callout_claim_response)

    def get_available_drops(self, channel_id: str) -> DropsHighlightServiceAvailableDropsResponse | None:
        """
        Gets the ids of all drops that are available.
        :param channel_id: The id of the channel to check.
        :return: The response.
        """
        json_data = copy.deepcopy(GQLOperations.DropsHighlightService_AvailableDrops)
        json_data["variables"] = {"channelID": channel_id}
        return self.post_gql_request(json_data, self.parser.parse_drops_highlight_service_available_drops)

    def get_inventory(self) -> InventoryResponse | None:
        """
        Gets the user's Inventory.
        :return: The response.
        """
        return self.post_gql_request(GQLOperations.Inventory, self.parser.parse_inventory_response)

    def get_viewer_drops_dashboard(self) -> ViewerDropsDashboardResponse | None:
        """
        Gets the viewer drops dashboard.
        :return: The response.
        """
        return self.post_gql_request(
            GQLOperations.ViewerDropsDashboard, self.parser.parse_viewer_drops_dashboard_response
        )

    def get_drop_campaign_details(self, campaign_ids: list[str]) -> list[DropCampaignDetailsResponse]:
        """
        Gets the drop campaign details for the campaigns with the given ids.
        :param campaign_ids: The ids of the campaigns.
        :return: The response.
        """
        result = []
        # Batch the requests into chunks of 20
        chunks = create_chunks(campaign_ids, 20)
        for chunk in chunks:
            json_data = []
            for campaign in chunk:
                json_data.append(copy.deepcopy(GQLOperations.DropCampaignDetails))
                json_data[-1]["variables"] = {
                    "dropID": campaign["id"],
                    "channelLogin": f"{self.client_session.login.get_user_id()}",
                }

            # Don't automatically parse it here, the response should be a list
            response = self.post_gql_request(json_data, lambda x: x)
            if not isinstance(response, list):
                logger.debug("Unexpected campaigns response format, skipping chunk")
                continue
            for item in response:
                drop_campaign = self.parser.parse_drop_campaign_details_response(item)
                if drop_campaign is not None:
                    result.append(drop_campaign)
        return result

    def claim_drop_rewards(self, drop_instance_id: str) -> DropsPageClaimDropsResponse | None:
        """
        Claims the rewards for the drop with the given id.
        :param drop_instance_id: The id of the drop.
        :return: The response.
        """
        json_data = copy.deepcopy(GQLOperations.DropsPage_ClaimDropRewards)
        json_data["variables"] = {
            "input": {"dropInstanceID": drop_instance_id}
        }
        return self.post_gql_request(json_data, self.parser.parse_drop_page_claim_drop_rewards)

    def get_user_points_contribution(self, username: str) -> UserPointsContributionResponse | None:
        """
        Gets the user points contribution for streamer with the given username.
        :param username: The username of the streamer.
        :return: The response.
        """
        json_data = copy.deepcopy(GQLOperations.UserPointsContribution)
        json_data["variables"] = {"channelLogin": username}
        return self.post_gql_request(json_data, self.parser.parse_user_points_contribution)

    def contribute_to_community_goal(self, channel_id, goal_id, amount):
        """
        Contributes the given amount of channel points to the given community goal.
        :param channel_id: The id of the channel running the goal.
        :param goal_id: The id of the goal.
        :param amount: The amount to contribute.
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
        self.post_gql_request(json_data, self.parser.parse_contribute_community_points_community_goal)
