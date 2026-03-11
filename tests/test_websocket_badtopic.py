import json
import unittest
from types import SimpleNamespace

from TwitchChannelPointsMiner.classes.WebSocketsPool import WebSocketsPool
from TwitchChannelPointsMiner.classes.entities.PubsubTopic import PubsubTopic


class WebSocketBadTopicTest(unittest.TestCase):
    def test_err_badtopic_drops_topic_from_resubscribe_lists(self):
        topic = PubsubTopic("community-points-user-v1", user_id="123")
        nonce = "nonce-1"
        ws = SimpleNamespace(
            index=0,
            listen_nonces={nonce: topic},
            topics=[topic],
            pending_topics=[topic],
            twitch=SimpleNamespace(twitch_login=SimpleNamespace(username="tester")),
        )

        WebSocketsPool.on_message(
            ws,
            json.dumps(
                {
                    "type": "RESPONSE",
                    "nonce": nonce,
                    "error": "ERR_BADTOPIC",
                }
            ),
        )

        self.assertNotIn(topic, ws.topics)
        self.assertNotIn(topic, ws.pending_topics)
        self.assertNotIn(nonce, ws.listen_nonces)


if __name__ == "__main__":
    unittest.main()
