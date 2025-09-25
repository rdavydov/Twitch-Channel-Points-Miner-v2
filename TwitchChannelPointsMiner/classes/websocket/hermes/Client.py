import abc
import json
import logging
import threading
from datetime import datetime
from enum import Enum
from threading import Thread
from typing import Tuple
from uuid import uuid4

from websocket import WebSocketApp, WebSocketConnectionClosedException

from TwitchChannelPointsMiner.classes.Settings import Settings
from TwitchChannelPointsMiner.classes.TwitchLogin import TwitchLogin
from TwitchChannelPointsMiner.classes.entities.PubsubTopic import PubsubTopic
from TwitchChannelPointsMiner.classes.websocket.hermes.data.Decoders import ResponseDecoder
from TwitchChannelPointsMiner.classes.websocket.hermes.data.Encoders import RequestEncoder
from TwitchChannelPointsMiner.classes.websocket.hermes.data.request import Request
from TwitchChannelPointsMiner.classes.websocket.hermes.data.request.Authenticate import AuthenticateRequest
from TwitchChannelPointsMiner.classes.websocket.hermes.data.request.Subscribe import SubscribePubSubRequest
from TwitchChannelPointsMiner.classes.websocket.hermes.data.response import (
    WelcomeResponse, AuthenticateResponse,
    SubscribeResponse, NotificationResponse, KeepaliveResponse, ReconnectResponse
)
from TwitchChannelPointsMiner.utils import internet_connection_available, combine

logger = logging.getLogger(__name__)


class State(Enum):
    """Enum representing the States a Client can be in."""
    UNOPENED = 0
    """The Client has yet to be opened, open and on_open haven't been called."""
    UNWELCOMED = 1
    """The Client has yet to receive a welcome message."""
    UNAUTHENTICATED = 2
    """The Client has yet to be authenticated, it's waiting for an AuthenticateResponse."""
    OPEN = 3
    """The Client has been opened and authenticated. It can send and receive messages."""
    CLOSED = 4
    """The Client has been closed or is closing. It should not be reopened, instead create a new Client."""

    def __repr__(self):
        return self.name.capitalize()

    def __str__(self):
        return repr(self)


class HermesClient(WebSocketApp):
    """A WebSocket client that integrates with the Hermes API."""

    def __init__(
        self, index: int, url: str, auth: TwitchLogin, pending_topics: list[PubsubTopic], json_encoder: RequestEncoder,
        json_decoder: ResponseDecoder
    ):
        """
        Creates a new Client.
        :param index: The unique index of this Client.
        :param url: The URL this Client should connect to.
        :param auth: The authentication object used to create AuthenticateRequests.
        :param pending_topics: The initial list of Topics this Client should subscribe to.
        :param json_encoder: The Request JSON encoder.
        :param json_decoder: The Response JSON decoder.
        """
        super().__init__(
            url,
            on_open=HermesClient.on_open,
            on_message=HermesClient.on_message,
            on_close=HermesClient.on_close,
            on_error=HermesClient.on_error,
        )
        self.index = index
        self.url = url
        self.auth = auth
        self.pending_topics = pending_topics
        self.json_encoder = json_encoder
        self.json_decoder = json_decoder

        self.id = str(uuid4())
        """The unique id of this Client."""

        self.state = State.UNOPENED
        """The current state of this Client."""

        self.subscriptions: dict[str, Tuple[PubsubTopic, SubscribePubSubRequest]] = {}
        """The topics this Client subscribes to."""

        self.listeners: list["HermesWebSocketListener"] = []
        """The listeners this Client will send various message events to."""

        self.last_message_timestamp = None
        """The timestamp of the last message."""

        self.last_message_identifier = None
        """The identifier of the last message."""

        self.message_timeout_seconds = 20
        """The amount of seconds this client should wait for message before timing out."""

        self.last_message_time = datetime.now()
        """The last time a message was received or the time this Client was created."""

        self.created_timeout_seconds = 300
        """The amount of seconds this Client should wait in an uninitialised state."""

        self.created_time = datetime.now()
        """The time when this Client was created."""

        self.pending_topics_lock = threading.Lock()
        """A lock to avoid simultaneous access to pending_topics."""

        self.close_lock = threading.Lock()
        """A lock to avoid manually closing this Client multiple times."""

        self.thread_ws = None
        """The Thread running this Client or None if open hasn't been called."""

    def describe(self):
        return f"#{self.index}" if Settings.logger.less else f"#{self.index} - {self.id}"

    def open(self):
        """Opens this client by calling `run_forever` in a new thread."""
        if self.state == State.UNOPENED:
            if self.thread_ws is None:
                if Settings.disable_ssl_cert_verification is True:
                    import ssl

                    self.thread_ws = Thread(
                        target=lambda: self.run_forever(
                            sslopt={"cert_reqs": ssl.CERT_NONE},
                            origin="https://www.twitch.tv",
                        )
                    )
                    logger.warning("SSL certificate verification is disabled! Be aware!")
                else:
                    self.thread_ws = Thread(target=lambda: self.run_forever(origin="https://www.twitch.tv"))
                self.thread_ws.daemon = True
                self.thread_ws.name = f"WebSocket #{self.index}"
                self.thread_ws.start()
            else:
                logger.warning(f"{self.describe()}: Cannot open Client, thread already running")
        else:
            logger.warning(f"{self.describe()}: Cannot open Client, wrong state: {self.state}")

    def close(self) -> None:
        """Closes this client, if it is already closed it does nothing."""
        do_close = False
        with self.close_lock:
            if self.state is not State.CLOSED:
                self.state = State.CLOSED
                do_close = True
        if do_close:
            super().close()

    def __send_request(self, request: Request):
        """
        Sends a request to the remote server.
        :param request: The Request to send.
        :return: True if the request was sent, False otherwise.
        """
        try:
            data = self.json_encoder.encode(request)
            logger.debug(
                f"{self.describe()} - Send: {"AuthenticateRequest(REDACTED)" if isinstance(request, AuthenticateRequest) else data}"
            )
            self.send(data)
            return True
        except WebSocketConnectionClosedException:
            # This is the intended way to detect closures during send so no need to call on_error.
            # Additionally, on_close should get called by the underlying library so no need to call that either.
            logger.warning(f"{self.describe()} - Cannot send, WebSocket is closed")
            self.state = State.CLOSED
            return False

    def send_request(self, request: Request):
        """
        Sends a request to the remote server. If the connection is not yet open the request is queued. If the client is
        already closed nothing happens.
        :param request: The Request to send.
        :return: True if the request was sent, False otherwise.
        """
        if self.state == State.OPEN:
            return self.__send_request(request)
        elif self.state in {State.UNOPENED, State.UNWELCOMED, State.UNAUTHENTICATED}:
            logger.warning(f"{self.describe()} - Cannot send, WebSocket is not yet open: {self.state}")
        else:
            logger.warning(f"{self.describe()} - Cannot send, WebSocket is closed")
        return False

    def authenticate(self):
        """
        Authenticate this client by sending an authentication request. If the client is not in an UNAUTHENTICATED state
        it does nothing.
        """
        if self.state is State.UNAUTHENTICATED:
            if not self.__send_request(AuthenticateRequest.create(str(self.auth.get_auth_token()))):
                logger.warning(f"{self.describe()} - Failed to send Authentication request")
        else:
            logger.warning(f"{self.describe()} - Cannot authenticate, wrong state {self.state}")

    def subscribe_now(self, topic: PubsubTopic):
        """
        Subscribes to the given topic now rather than adding it to the queue.
        :param topic: The topic to subscribe to.
        :return: True if the subscription was successful, False otherwise.
        """
        request = SubscribePubSubRequest.create(topic)
        if self.send_request(request):
            self.subscriptions[request.subscribe.id] = (topic, request)
            return True
        else:
            return False

    def subscribe(self, topic: PubsubTopic):
        """
        If open, the client subscribes to the given topic now. Otherwise, it adds it to the pending topics queue.
        :param topic: The topic to subscribe to.
        """
        with self.pending_topics_lock:
            # Acquire the lock early to avoid the client becoming Open before adding the topic to the queue
            if self.state == State.OPEN:
                self.subscribe_now(topic)
            else:
                self.pending_topics.append(topic)

    def elapsed_created(self) -> float:
        """
        Calculates the amount of time, in seconds, since this client was created.
        :return:
        """
        return (datetime.now() - self.created_time).total_seconds()

    def elapsed_last_message(self) -> float:
        """
        Calculates the amount of time, in seconds, since the last message.
        :return: The duration in seconds.
        """
        return (datetime.now() - self.last_message_time).total_seconds()

    def stale(self):
        """
        Checks if the connection is stale, either it's timed out because the last message was not received recently
        enough (and an internet connection is available), or it's been sitting uninitialised for too long, or it's
        closed. Keep in mind that this also expects authentication to be completed in a timely manner.

        :return: True if the connection is stale, False otherwise.
        """
        if self.state == State.CLOSED:
            # If we're closed then we're stale if something wants to use us
            logger.debug(f"{self.describe()} - Stale due to being closed")
            return True
        elif self.state == State.UNOPENED:
            if self.elapsed_created() > self.created_timeout_seconds and internet_connection_available():
                # If we're Unopened and still haven't been opened in this time then we're stale
                logger.debug(f"{self.describe()} - Stale due to being Unopened and sitting idle too long")
                return True
        else:
            if self.elapsed_last_message() > self.message_timeout_seconds and internet_connection_available():
                # If we're past Unopened but not closed we should still be getting at least keepalives
                logger.debug(f"{self.describe()} - Stale due to no recent messages")
                return True
        return False

    def topic(self, subscription_id: str) -> PubsubTopic | None:
        """
        Gets the topic for the Subscription with the given id.
        :param subscription_id: The id of the subscription for which to get the topic.
        :return: The topic or None if the subscription does not exist.
        """
        subscription = self.subscriptions.get(subscription_id)
        if subscription is None:
            return None
        else:
            return subscription[0]

    def all_topics(self) -> list[PubsubTopic]:
        """
        Gets a list of all pending and subscribed topics.
        :return: All topics for this client.
        """
        with self.pending_topics_lock:
            return list(combine(map(lambda pair: pair[0], self.subscriptions.values()), self.pending_topics))

    def add_listener(self, listener: "HermesWebSocketListener"):
        """
        Adds a listener to this client.
        :param listener: The listener to add.
        """
        self.listeners.append(listener)

    def subscribed(self, topic: PubsubTopic) -> bool:
        """
        Checks whether this client has subscribed to the given topic.
        :param topic: The topic to check.
        :return: True if this client is subscribed to the given topic.
        """
        topic_str = str(topic)
        for self_topic in self.all_topics():
            if str(self_topic) == topic_str:
                return True
        return False

    def subscribe_pending(self):
        """
        Subscribes to the pending subscriptions.

        Ensures that any failed subscriptions remain in the pending queue.
        """
        if self.state == State.OPEN:
            with self.pending_topics_lock:
                while len(self.pending_topics) > 0:
                    topic = self.pending_topics.pop()
                    try:
                        self.subscribe_now(topic)
                    except Exception as e:
                        # Put the failed topic back in the list and propagate the error
                        self.pending_topics.append(topic)
                        raise e

        else:
            logger.warning(f"{self.describe()} - Cannot subscribe to pending subscriptions, state is {self.state}")

    @staticmethod
    def on_open(client: "HermesClient"):
        """
        Sets the client's state to UNWELCOMED.
        :param client: The client that has opened.
        """
        logger.debug(f"Hermes client opened: index={client.index}, id='{client.id}'")
        client.state = State.UNWELCOMED

    @staticmethod
    def on_message(client: "HermesClient", message: str):
        """
        Parses the message and passes it to the appropriate message listener.
        :param client: The client that received the message.
        :param message: The message that was received.
        """
        logger.debug(f"{client.describe()} - Received: {message.strip()}")
        client.last_message_time = datetime.now()
        try:
            response = client.json_decoder.decode(message)
            try:
                if isinstance(response, WelcomeResponse):
                    for listener in client.listeners:
                        listener.on_welcome(client, response.welcome.keepalive_sec)
                elif isinstance(response, AuthenticateResponse):
                    for listener in client.listeners:
                        listener.on_authenticate(client, response)
                elif isinstance(response, SubscribeResponse):
                    for listener in client.listeners:
                        listener.on_subscribe(client, response)
                elif isinstance(response, KeepaliveResponse):
                    for listener in client.listeners:
                        listener.on_keepalive(client)
                elif isinstance(response, NotificationResponse):
                    for listener in client.listeners:
                        listener.on_notification(client, response)
                elif isinstance(response, ReconnectResponse):
                    for listener in client.listeners:
                        listener.on_reconnect(client, response.reconnect.url)
                else:
                    logger.error(f"{client.describe()} - Unknown response: {response}")
            except Exception as e:
                if isinstance(response, NotificationResponse):
                    topic = client.topic(response.notification.subscription.id)
                    logger.error(
                        f"{client.describe()} - Exception raised for topic: {str(topic)} and message: {message}",
                        exc_info=e
                    )
                else:
                    logger.error(f"{client.describe()} - Exception raised for response: {response}", exc_info=e)
                HermesClient.on_error(client, e)
        except (json.JSONDecodeError, ValueError) as e:
            HermesClient.on_error(client, e)

    @staticmethod
    def on_close(client: "HermesClient", status_code, reason):
        """
        Called when the client closes.
        :param client: The client that has closed.
        :param status_code: The WebSocket close status code.
        :param reason: The reason the client was closed.
        """
        logger.debug(f"{client.describe()} - WebSocket closed: {status_code} - {reason}")
        client.state = State.CLOSED
        try:
            for listener in client.listeners:
                listener.on_close(client, status_code, reason)
        except Exception as e:
            HermesClient.on_error(client, e)

    @staticmethod
    def on_error(client: "HermesClient", error):
        """
        Called when an error occurs.
        :param client: The client that has encountered an error.
        :param error: The error that occurred.
        """
        # Connection lost | [WinError 10054] An existing connection was forcibly closed by the remote host
        # Connection already closed | Connection is already closed (raise WebSocketConnectionClosedException)
        try:
            for listener in client.listeners:
                listener.on_error(client, error)
        except Exception as e2:
            logger.error(f"{client.describe()} - Error while handling another error - '{error}'", exc_info=e2)


class HermesWebSocketListener(abc.ABC):
    """Abstract base class for an object that can receive events from Hermes Clients."""

    def on_welcome(self, client: HermesClient, keepalive_secs: int):
        """
        Called when a Client receives a welcome message.
        :param client: The Client that received the welcome message.
        :param keepalive_secs: The keepalive timeout in seconds.
        """
        pass

    def on_authenticate(self, client: HermesClient, response: AuthenticateResponse):
        """
        Called when a Client receives an AuthenticateResponse.
        :param client: The Client that received the response.
        :param response: The response that was received.
        """
        pass

    def on_subscribe(self, client: HermesClient, response: SubscribeResponse):
        """
        Called when a Client receives a SubscribeResponse.
        :param client: The Client that received the response.
        :param response: The response that was received.
        """
        pass

    def on_keepalive(self, client: HermesClient):
        """
        Called when a Client receives a KeepaliveResponse.
        :param client: The Client that received the response.
        :return:
        """
        pass

    def on_notification(self, client: HermesClient, response: NotificationResponse):
        """
        Called when a Client receives a NotificationResponse.
        :param client: The Client that received the response.
        :param response: The response that was received.
        """
        pass

    def on_reconnect(self, client: HermesClient, url: str):
        """
        Called when a Client receives a ReconnectResponse.
        :param client: The Client that received the response.
        :param url: The URL in the response.
        """
        pass

    def on_close(self, client: HermesClient, code: int, reason: str):
        """
        Called when a Client closes.
        :param client: The Client that closed.
        :param code: The WebSocket close status code.
        :param reason: The close reason.
        """
        pass

    def on_error(self, client: HermesClient, error: Exception):
        """
        Called when a Client experiences an error.
        :param client: The Client that experienced the error.
        :param error: The error that occurred.
        """
        pass
