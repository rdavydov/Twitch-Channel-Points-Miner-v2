class Authorization:
    def __init__(self, is_forbidden: bool, forbidden_reason_code: str):
        self.is_forbidden = is_forbidden
        self.forbidden_reason_code = forbidden_reason_code

    def __repr__(self):
        return f"Authorization({self.__dict__})"


class PlaybackAccessTokenResponse:
    def __init__(self, value: str, signature: str, authorization: Authorization):
        self.value = value
        self.signature = signature
        self.authorization = authorization

    def __repr__(self):
        return f"StreamPlaybackAccessToken({self.__dict__})"
