import logging
import random
import threading
import time
from typing import Iterable

from websocket import WebSocketConnectionClosedException

from TwitchChannelPointsMiner.classes.PubSub import MessageListener
from TwitchChannelPointsMiner.classes.Twitch import Twitch
from TwitchChannelPointsMiner.classes.TwitchLogin import TwitchLogin
from TwitchChannelPointsMiner.classes.entities.Message import Message
from TwitchChannelPointsMiner.classes.entities.PubsubTopic import PubsubTopic
from TwitchChannelPointsMiner.classes.websocket.Pool import WebSocketPool
from TwitchChannelPointsMiner.classes.websocket.hermes.Client import HermesClient, State, HermesWebSocketListener
from TwitchChannelPointsMiner.classes.websocket.hermes.data.Decoders import ResponseDecoder
from TwitchChannelPointsMiner.classes.websocket.hermes.data.Encoders import RequestEncoder
from TwitchChannelPointsMiner.classes.websocket.hermes.data.response import (NotificationResponse, AuthenticateResponse)
from TwitchChannelPointsMiner.utils import internet_connection_available

logger = logging.getLogger(__name__)


class HermesWebSocketPool(WebSocketPool, HermesWebSocketListener):
    """WebSocketPool that manages HermesClients."""

    def __init__(
        self, url: str, twitch: Twitch, listeners: Iterable[MessageListener], request_encoder: RequestEncoder,
        response_decoder: ResponseDecoder, max_subscriptions_per_client: int = 50
    ):
        """
        Creates a new pool.
        :param url: The URL to which clients will connect.
        :param twitch: The Twitch API instance.
        :param listeners: The initial MessageListeners that will receive messages from the clients.
        :param request_encoder: The encoder for requests.
        :param response_decoder: The decoder for responses.
        :param max_subscriptions_per_client: The maximum number of subscriptions each client can have.
        """
        self.url = url
        self.twitch = twitch
        self.request_encoder = request_encoder
        self.response_decoder = response_decoder
        self.max_subscriptions_per_client = max_subscriptions_per_client

        self.clients: list[HermesClient] = []
        """The list of clients managed by this pool."""

        self.pubsub_message_listeners = [listener for listener in listeners]
        """The list of pubsub messages listeners that will receive messages from the clients."""

        self.force_close = False
        """True if this pool is closed/closing."""

        self.__lock = threading.Lock()
        """Lock to prevent improper variable access in a multithreaded context."""

    def topic(self, subscription_id: str) -> PubsubTopic | None:
        """
        Returns the PubSubTopic for the given subscription id or None if the subscription does not exist.
        :param subscription_id: The ID of the subscription.
        :return: The PubSubTopic or None.
        """
        for client in self.clients:
            if (topic := client.topic(subscription_id)) is not None:
                return topic
        return None

    def __create_new_client(
        self, auth: TwitchLogin, topics: list[PubsubTopic], index: int | None = None
    ) -> HermesClient:
        """
        Creates a new HermesClient.
        :param auth: The TwitchLogin object that provides authentication tokens.
        :param topics: The list of PubSubTopic topics that the client should subscribe to.
        :param index: The index at which to create the new client. If None, the new client will be appended to the list.
        :return: The new HermesClient.
        """
        try:
            index = index if index is not None else len(self.clients)
            logger.debug(f'Creating new HermesClient at index {index}')
            client = HermesClient(index, self.url, auth, topics, self.request_encoder, self.response_decoder)
            client.add_listener(self)
            if index == len(self.clients):
                self.clients.append(client)
            else:
                self.clients[index] = client
            return client
        except Exception as e:
            logger.error("Failed to create new Hermes WebSocket client", exc_info=e)
            raise e

    def __next_available_client(self) -> HermesClient:
        """
        Gets the next client that can subscribe to new topics.
        Creates a new one if all clients are unavailable.
        :return: The client.
        """
        client = next(
            (
                client for client in self.clients if
                client.state is not State.CLOSED and
                len(client.all_topics()) < self.max_subscriptions_per_client
            ),
            None
        )
        if client is None:
            client = self.__create_new_client(self.twitch.twitch_login, [])
            client.open()
        return client

    def __subscribed(self, topic: PubsubTopic) -> bool:
        """
        Checks if any client is subscribed to the given topic.
        :param topic: The topic to check.
        :return: Returns True if any client is subscribed to the given topic.
        """
        return any(client.subscribed(topic) for client in self.clients)

    def submit(self, topic: PubsubTopic):
        """
        Subscribes to the given topic.
        :param topic: The topic to subscribe to.
        """
        with self.__lock:
            if self.__subscribed(topic):
                logger.debug(f"Already subscribed to topic, {topic}")
            else:
                self.__next_available_client().subscribe(topic)

    def __reconnect(self, client: HermesClient):
        """
        Reconnects the given client.
        :param client: The client to reconnect.
        """
        with self.__lock:
            # First ensure that the client is closed as a catch-all for dangling clients
            client.close()
            if self.force_close:
                # No need to reconnect if the pool is closed
                return
            if self.clients[client.index].id != client.id:
                # This can happen when we call __reconnect before the client connection has closed, i.e. when Twitch
                # sends a "reconnect" message. This results in the client triggering both an on_reconnect and an
                # on_close event. We don't want to reconnect twice, which would create multiple websocket clients per
                # index, so this case can be safely ignored.
                logger.debug(f'{client.describe()} already reconnecting')
                return
            new_client = self.__create_new_client(self.twitch.twitch_login, client.all_topics(), client.index)
        # Avoid holding the lock while sleeping, we've already updated the list anyway
        logger.debug(f"{client.describe()} - Reconnecting to Twitch Hermes server in ~30 seconds")
        time.sleep(30)
        while not internet_connection_available() and not self.force_close:
            random_sleep = random.randint(1, 3)
            logger.warning(f"{client.describe()} - No internet connection available! Retrying websocket reconnection after {random_sleep}m")
            time.sleep(random_sleep * 60)
        if not self.force_close:
            # Don't bother opening the new client if between creation and now the pool has closed
            new_client.open()

    def on_welcome(self, client: HermesClient, keepalive_secs: int):
        """
        Sets the keepalive timeout on the client, sets its state to UNAUTHENTICATED, and begins authentication.
        :param client: The welcomed client.
        :param keepalive_secs: The keepalive timeout in seconds.
        """
        client.message_timeout_seconds = keepalive_secs + 5
        client.state = State.UNAUTHENTICATED
        client.authenticate()

    def on_authenticate(self, client: HermesClient, response: AuthenticateResponse):
        """
        Checks the authentication response for errors and closes the client if necessary.
        :param client: The authenticated client.
        :param response: The authentication response.
        """
        if response.has_error():
            logger.error(f"{client.describe()} - Authentication error, {response}")
            client.close()
        else:
            logger.debug(f"{client.describe()} - Authentication success")
            client.state = State.OPEN
            client.subscribe_pending()

    def on_notification(self, client: HermesClient, response: NotificationResponse):
        """
        Propagates the notification to the listeners.
        :param client: The client that received the notification.
        :param response: The notification response.
        """
        notification = response.notification
        if isinstance(notification, NotificationResponse.PubSubData):
            topic = self.topic(notification.subscription.id)
            if topic is not None:
                message = Message({"topic": str(topic), "message": notification.pubsub})
                if (
                        client.last_message_identifier is not None
                        and client.last_message_timestamp is not None
                        and client.last_message_timestamp == message.timestamp
                        and client.last_message_identifier == message.identifier
                ):
                    return
                client.last_message_timestamp = message.timestamp
                client.last_message_identifier = message.identifier

                for listener in self.pubsub_message_listeners:
                    listener.on_message(message)
            else:
                logger.warning(
                    f"{client.describe()} - Unable to find topic for subscription {notification.subscription.id}"
                )
        else:
            logger.warning(f"{client.describe()} - Received unknown notification type {type(notification)}")

    def on_close(self, client: HermesClient, code: int, reason: str):
        """
        Tries to reconnect the client that closed.
        :param client: The client that closed.
        :param code: The close status code.
        :param reason: The close reason.
        """
        self.__reconnect(client)

    def on_reconnect(self, client: HermesClient, url: str):
        """
        Tries to reconnect the client with the given id.

        Ignores the given url and connects to the default one to avoid a 4122 "invalid challenge" server error during
        authentication.
        :param client: The client to reconnect.
        :param url: The new URL to reconnect to.
        """
        self.__reconnect(client)

    def on_error(self, client: HermesClient, error: Exception):
        """
        Logs the error. Additionally, reconnects if the error is a WebSocketConnectionClosedException.
        :param client: The client that's errored.
        :param error: The error Exception.
        """
        # Ignore the stack trace for socket closures, we'll get additional info in the on_close
        is_closed_error = isinstance(error, WebSocketConnectionClosedException)
        if is_closed_error:
            logger.debug(f"{client.describe()} - WebSocket error: {error}")
            self.__reconnect(client)
        else:
            # Don't pass the error since we can't actually confirm it's an Exception
            logger.error(f"{client.describe()} - WebSocket error: {error}", exc_info=isinstance(error, BaseException))

    def start(self):
        logger.debug(f"Starting Hermes WebSocket Pool")

    def end(self):
        logger.debug(f"Closing Hermes WebSocket Pool")
        self.force_close = True
        with self.__lock:
            for client in self.clients:
                try:
                    client.close()
                except Exception as e:
                    logger.error(f"{client.describe()} - Error closing client", exc_info=e)
            self.clients.clear()

    def check_stale_connections(self):
        logger.debug(f"Checking stale connections")
        for client_index in range(len(self.clients)):
            client = self.clients[client_index]
            if client.stale():
                self.__reconnect(client)
