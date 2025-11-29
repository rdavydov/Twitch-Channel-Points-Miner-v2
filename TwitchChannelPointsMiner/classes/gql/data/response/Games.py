class Game:
    def __init__(self, _id: str):
        self.id = _id

    def __repr__(self):
        return f"Game({self.__dict__})"

    def __eq__(self, other):
        return isinstance(other, Game) and self.id == other.id
