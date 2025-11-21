from TwitchChannelPointsMiner.classes.gql.data.response.BroadcastSettings import BroadcastSettings
from TwitchChannelPointsMiner.classes.gql.data.response.Stream import Stream


class User:
    def __init__(
        self,
        _id: str,
        profile_url: str,
        display_name: str,
        login: str,
        profile_image_url: str,
        broadcast_settings: BroadcastSettings,
        stream: Stream | None,
    ):
        self.id = _id
        self.profile_url = profile_url
        self.display_name = display_name
        self.login = login
        self.profile_image_url = profile_image_url
        self.broadcast_settings = broadcast_settings
        self.stream = stream

    def __repr__(self):
        return f"User({self.__dict__})"


class VideoPlayerStreamInfoOverlayChannelResponse:
    def __init__(self, user: User):
        self.user = user

    def __repr__(self):
        return f"VideoPlayerStreamInfoOverlayChannelResponse({self.__dict__})"
