from TwitchChannelPointsMiner.classes.gql.data.response import Games


class GameBroadcastSettings(Games.Game):
    def __init__(
        self,
        _id: str,
        display_name: str,
        name: str,
    ):
        super().__init__(_id)
        self.display_name = display_name
        self.name = name

    def __repr__(self):
        return f"Game({self.__dict__})"


class BroadcastSettings:
    def __init__(
        self,
        _id: str,
        title: str,
        game: GameBroadcastSettings | None,
    ):
        self.id = _id
        self.title = title
        self.game = game

    def __repr__(self):
        return f"BroadcastSettings({self.__dict__})"
