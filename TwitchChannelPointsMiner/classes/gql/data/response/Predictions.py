class Error:
    def __init__(self, code: str):
        self.code = code

    def __repr__(self):
        return f"Error({self.__dict__})"


class MakePredictionResponse:
    def __init__(self, error: Error | None):
        self.error = error

    def __repr__(self):
        return f"MakePredictionResponse({self.__dict__})"
