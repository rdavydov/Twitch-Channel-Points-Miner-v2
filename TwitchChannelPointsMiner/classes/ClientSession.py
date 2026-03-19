import logging
import string
import uuid
from secrets import choice

from TwitchChannelPointsMiner.classes.TwitchLogin import TwitchLogin
from TwitchChannelPointsMiner.constants import CLIENT_VERSION

logger = logging.getLogger(__name__)


class ClientSession:
    """Represents a Client Session with Twitch."""

    def __init__(
        self,
        login: TwitchLogin,
        user_agent: str,
        version: str | None = None,
        device_id: str | None = None,
        session_id: str | None = None,
    ):
        self.login = login
        self.user_agent = user_agent
        self.version: str = version if version is not None else CLIENT_VERSION
        self.device_id = (
            device_id
            if device_id
            else "".join(
                choice(string.ascii_letters + string.digits) for _ in range(32)
            )
        )
        self.session_id = session_id if session_id is not None else str(uuid.uuid4())
