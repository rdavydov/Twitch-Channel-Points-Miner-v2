class Tag:
    def __init__(self, _id: str, localized_name: str):
        self.id = _id
        self.localized_name = localized_name

    def __repr__(self):
        return f"Tag({self.__dict__})"


class Stream:
    def __init__(self, _id: str, viewers_count: int, tags: list[Tag]):
        self.id = _id
        self.viewers_count = viewers_count
        self.tags = tags

    def __repr__(self):
        return f"Stream({self.__dict__})"
