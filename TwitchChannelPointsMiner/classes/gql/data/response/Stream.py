class Tag:
    def __init__(self, _id: str):
        self.id = _id

    def __repr__(self):
        return f"Tag({self.__dict__})"


class Stream:
    def __init__(
        self,
        _id: str,
        viewers_count: int,
        tags: list,  # Unclear what the type is
    ):
        self.id = _id
        self.viewers_count = viewers_count
        self.tags = tags

    def __repr__(self):
        return f"Stream({self.__dict__})"
