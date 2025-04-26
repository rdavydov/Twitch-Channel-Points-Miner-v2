import json
import logging
import time

from websocket import WebSocketApp, WebSocketConnectionClosedException

from TwitchChannelPointsMiner.utils import create_nonce

logger = logging.getLogger(__name__)


class TwitchWebSocket(WebSocketApp):
    def __init__(self, index, parent_pool, *args, **kw):
        super().__init__(*args, **kw)
        self.index = index

        self.parent_pool = parent_pool
        self.is_closed = False
        self.is_opened = False

        self.is_reconnecting = False
        self.forced_close = False

        # Custom attribute
        self.topics = []
        self.pending_topics = []

        self.twitch = parent_pool.twitch
        self.streamers = parent_pool.streamers
        self.events_predictions = parent_pool.events_predictions

        self.last_message_timestamp = None
        self.last_message_type_channel = None

        self.last_pong = time.time()
        self.last_ping = time.time()

    # def close(self):
    #     self.forced_close = True
    #     super().close()

    def listen(self, topic, auth_token=None):
        data = {"topics": [str(topic)]}
        if topic.is_user_topic() and auth_token is not None:
            data["auth_token"] = auth_token
        nonce = create_nonce()
        self.send({"type": "LISTEN", "nonce": nonce, "data": data})

    def ping(self):
        self.send({"type": "PING"})
        self.last_ping = time.time()

    def send(self, request):
        try:
            request_str = json.dumps(request, separators=(",", ":"))
            logger.debug(f"#{self.index} - Send: {request_str}")
            super().send(request_str)
        except WebSocketConnectionClosedException:
            self.is_closed = True

    def elapsed_last_pong(self):
        return (time.time() - self.last_pong) // 60

    def elapsed_last_ping(self):
        return (time.time() - self.last_ping) // 60
