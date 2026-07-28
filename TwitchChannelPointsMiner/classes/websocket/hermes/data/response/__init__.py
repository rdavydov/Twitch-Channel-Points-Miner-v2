from .Authenticate import AuthenticateResponse
from .Base import Subscription
from .Keepalive import KeepaliveResponse
from .Notification import NotificationResponse
from .Reconnect import ReconnectResponse
from .Subscribe import SubscribeResponse
from .Welcome import WelcomeResponse

type Response = WelcomeResponse | AuthenticateResponse | KeepaliveResponse | SubscribeResponse | NotificationResponse | ReconnectResponse
