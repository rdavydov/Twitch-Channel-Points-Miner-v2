import json
import logging
import random
import time
from threading import Thread
from typing import Iterable

from TwitchChannelPointsMiner.classes.PubSub import MessageListener
from TwitchChannelPointsMiner.classes.Settings import Settings
from TwitchChannelPointsMiner.classes.Twitch import Twitch
from TwitchChannelPointsMiner.classes.entities.Message import Message
from TwitchChannelPointsMiner.classes.websocket.Pool import WebSocketPool
from TwitchChannelPointsMiner.classes.websocket.pubsub.Client import PubSubWebSocket
from TwitchChannelPointsMiner.constants import WEBSOCKET
from TwitchChannelPointsMiner.utils import (
    internet_connection_available,
)

logger = logging.getLogger(__name__)


class PubSubWebSocketPool(WebSocketPool):
    __slots__ = ["ws", "twitch", "listeners"]

    def __init__(self, twitch: Twitch, listeners: Iterable[MessageListener]):
        self.ws = []
        self.twitch = twitch
        self.listeners = [listener for listener in listeners]
        self.forced_close = False

    """
    API Limits
    - Clients can listen to up to 50 topics per connection. Trying to listen to more topics will result in an error message.
    - We recommend that a single client IP address establishes no more than 10 simultaneous connections.
    The two limits above are likely to be relaxed for approved third-party applications, as we start to better understand third-party requirements.
    """

    def submit(self, topic):
        # Check if we need to create a new WebSocket instance
        if self.ws == [] or len(self.ws[-1].topics) >= 50:
            self.ws.append(self.__new(len(self.ws)))
            self.__start(-1)

        self.__submit(-1, topic)

    def __submit(self, index, topic):
        # Topic in topics should never happen. Anyway prevent any types of duplicates
        if topic not in self.ws[index].topics:
            self.ws[index].topics.append(topic)

        if self.ws[index].is_opened is False:
            self.ws[index].pending_topics.append(topic)
        else:
            self.ws[index].listen(topic, self.twitch.twitch_login.get_auth_token())

    def __new(self, index):
        return PubSubWebSocket(
            index=index,
            parent_pool=self,
            url=WEBSOCKET,
            on_message=PubSubWebSocketPool.on_message,
            on_open=PubSubWebSocketPool.on_open,
            on_error=PubSubWebSocketPool.on_error,
            on_close=PubSubWebSocketPool.on_close
            # on_close=PubSubWebSocketPool.handle_reconnection, # Do nothing.
        )

    def __start(self, index):
        if Settings.disable_ssl_cert_verification is True:
            import ssl

            thread_ws = Thread(
                target=lambda: self.ws[index].run_forever(
                    sslopt={"cert_reqs": ssl.CERT_NONE}
                )
            )
            logger.warning("SSL certificate verification is disabled! Be aware!")
        else:
            thread_ws = Thread(target=lambda: self.ws[index].run_forever())
        thread_ws.daemon = True
        thread_ws.name = f"WebSocket #{self.ws[index].index}"
        thread_ws.start()

    def start(self):
        logger.debug("Starting PubSub WebSocket Pool")

    def end(self):
        logger.debug(f"Closing PubSub WebSocket Pool")
        self.forced_close = True
        for index in range(0, len(self.ws)):
            self.ws[index].forced_close = True
            self.ws[index].close()

    def check_stale_connections(self):
        for index in range(0, len(self.ws)):
            if (
                    self.ws[index].is_reconnecting is False
                    and self.ws[index].elapsed_last_ping() > 10
                    and internet_connection_available() is True
            ):
                logger.info(
                    f"#{index} - The last PING was sent more than 10 minutes ago. Reconnecting to the WebSocket..."
                )
                PubSubWebSocketPool.handle_reconnection(self.ws[index])

    @staticmethod
    def on_open(ws):
        def run():
            ws.is_opened = True
            ws.ping()

            for topic in ws.pending_topics:
                ws.listen(topic, ws.twitch.twitch_login.get_auth_token())

            while ws.is_closed is False:
                # Else: the ws is currently in reconnecting phase, you can't do ping or other operation.
                # Probably this ws will be closed very soon with ws.is_closed = True
                if ws.is_reconnecting is False:
                    ws.ping()  # We need ping for keep the connection alive
                    time.sleep(random.uniform(25, 30))

                    if ws.elapsed_last_pong() > 5:
                        logger.info(
                            f"#{ws.index} - The last PONG was received more than 5 minutes ago"
                        )
                        PubSubWebSocketPool.handle_reconnection(ws)

        thread_ws = Thread(target=run)
        thread_ws.daemon = True
        thread_ws.start()

    @staticmethod
    def on_error(ws, error):
        # Connection lost | [WinError 10054] An existing connection was forcibly closed by the remote host
        # Connection already closed | Connection is already closed (raise WebSocketConnectionClosedException)
        logger.error(f"#{ws.index} - WebSocket error: {error}")

    @staticmethod
    def on_close(ws, close_status_code, close_reason):
        logger.info(f"#{ws.index} - WebSocket closed")
        # On close please reconnect automatically
        PubSubWebSocketPool.handle_reconnection(ws)

    @staticmethod
    def handle_reconnection(ws):
        # Reconnect only if ws.is_reconnecting is False to prevent more than 1 ws from being created
        if ws.is_reconnecting is False:
            # Close the current WebSocket.
            ws.is_closed = True
            ws.keep_running = False
            # Reconnect only if ws.forced_close is False (replace the keep_running)

            # Set the current socket as reconnecting status
            # So the external ping check will be locked
            ws.is_reconnecting = True

            if ws.forced_close is False:
                logger.info(
                    f"#{ws.index} - Reconnecting to Twitch PubSub server in ~60 seconds"
                )
                time.sleep(30)

                while internet_connection_available() is False:
                    random_sleep = random.randint(1, 3)
                    logger.warning(
                        f"#{ws.index} - No internet connection available! Retry after {random_sleep}m"
                    )
                    time.sleep(random_sleep * 60)

                # Why not create a new ws on the same array index? Let's try.
                self = ws.parent_pool
                # Create a new connection.
                self.ws[ws.index] = self.__new(ws.index)

                self.__start(ws.index)  # Start a new thread.
                time.sleep(30)

                for topic in ws.topics:
                    self.__submit(ws.index, topic)

    @staticmethod
    def on_message(ws: PubSubWebSocket, message: str):
        logger.debug(f"#{ws.index} - Received: {message.strip()}")
        response = json.loads(message)

        if response["type"] == "MESSAGE":
            # We should create a Message class ...
            message = Message(response["data"])

            # If we have more than one PubSub connection, messages may be duplicated
            # Check the concatenation between message_type.top.channel_id
            if (
                    ws.last_message_type_channel is not None
                    and ws.last_message_timestamp is not None
                    and ws.last_message_timestamp == message.timestamp
                    and ws.last_message_type_channel == message.identifier
            ):
                return

            ws.last_message_timestamp = message.timestamp
            ws.last_message_type_channel = message.identifier

            for listener in ws.parent_pool.listeners:
                listener.on_message(message)

        elif response["type"] == "RESPONSE" and len(response.get("error", "")) > 0:
            # raise RuntimeError(f"Error while trying to listen for a topic: {response}")
            error_message = response.get("error", "")
            logger.error(f"Error while trying to listen for a topic: {error_message}")

            # Check if the error message indicates an authentication issue (ERR_BADAUTH)
            if "ERR_BADAUTH" in error_message:
                # Inform the user about the potential outdated cookie file
                username = ws.twitch.twitch_login.username
                logger.error(
                    f"Received the ERR_BADAUTH error, most likely you have an outdated cookie file \"cookies\\{username}.pkl\". Delete this file and try again."
                )
                # Attempt to delete the outdated cookie file
                # try:
                #     cookie_file_path = os.path.join("cookies", f"{username}.pkl")
                #     if os.path.exists(cookie_file_path):
                #         os.remove(cookie_file_path)
                #         logger.info(f"Deleted outdated cookie file for user: {username}")
                #     else:
                #         logger.warning(f"Cookie file not found for user: {username}")
                # except Exception as e:
                #     logger.error(f"Error occurred while deleting cookie file: {str(e)}")

        elif response["type"] == "RECONNECT":
            logger.info(f"#{ws.index} - Reconnection required")
            PubSubWebSocketPool.handle_reconnection(ws)

        elif response["type"] == "PONG":
            ws.last_pong = time.time()
