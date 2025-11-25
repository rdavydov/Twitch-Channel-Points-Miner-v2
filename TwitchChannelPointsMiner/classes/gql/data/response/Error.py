class Error:
    def __init__(self, recoverable: bool, message: str, path: list[str] | None = None):
        self.recoverable = recoverable
        self.message = message
        self.path = path

    def __repr__(self):
        return f"Error({self.__dict__})"
