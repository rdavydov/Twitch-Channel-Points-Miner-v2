class GetIdFromLoginResponse:
    def __init__(self, _id: str):
        self.id = _id

    def __repr__(self):
        return f"GetIdFromLoginResponse({self.__dict__})"
