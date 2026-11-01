from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class DashboardSettings:
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 5000
    refresh_seconds: float = 300
    cooldown_seconds: float = 60
    request_interval_seconds: float = 1
    sample_seconds: float = 5
    timezone: str = "Europe/Budapest"

    def __post_init__(self):
        if self.host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("The dashboard must bind to a loopback address")
        if (
            isinstance(self.port, bool)
            or not isinstance(self.port, int)
            or not 1 <= self.port <= 65535
        ):
            raise ValueError("Invalid dashboard port")
        for name in (
            "refresh_seconds",
            "cooldown_seconds",
            "request_interval_seconds",
            "sample_seconds",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{name} must be positive and finite")
        from zoneinfo import ZoneInfo

        ZoneInfo(self.timezone)
