class Error:
    def __init__(self, message: str, path: list[str] | None = None):
        self.message = message
        self.path = path

    def __repr__(self):
        return f"Error({self.__dict__})"
