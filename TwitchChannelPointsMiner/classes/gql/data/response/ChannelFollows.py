from datetime import datetime

from TwitchChannelPointsMiner.classes.gql.data.response.Pagination import Paginated


class Follow:
    class SelfEdge:
        class Follower:
            def __init__(
                self,
                disable_notifications: bool,
                followed_at: datetime,
            ):
                self.disable_notifications = disable_notifications
                self.followed_at = followed_at

            def __repr__(self):
                return f"Follow({self.__dict__})"

        def __init__(
            self,
            can_follow: bool,
            follower: Follower,
        ):
            self.can_follow = can_follow
            self.follower = follower

        def __repr__(self):
            return f"Follow({self.__dict__})"

    def __init__(
        self,
        _id: str,
        banner_image_url: str | None,
        display_name: str,
        login: str,
        profile_image_url: str,
        _self: SelfEdge
    ):
        self._id = _id
        self.banner_image_url = banner_image_url
        self.display_name = display_name
        self.login = login
        self.profile_image_url = profile_image_url
        self.self = _self

    def __repr__(self):
        return f"Follow({self.__dict__})"


class ChannelFollowsResponse:
    def __init__(self, _id: str, follows: Paginated[Follow]):
        self._id = _id
        self.follows = follows

    def __repr__(self):
        return f"ChannelFollowsResponse({self.__dict__})"
