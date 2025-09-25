import platform
import re
import secrets
import socket
import time
from copy import deepcopy
from datetime import datetime, timezone
from os import path
from random import randrange
from typing import TypeVar, Iterable

import requests
from millify import millify

from TwitchChannelPointsMiner.constants import USER_AGENTS, GITHUB_url


def _millify(input, precision=2):
    return millify(input, precision)


def get_streamer_index(streamers: list, channel_id) -> int:
    try:
        return next(
            i for i, x in enumerate(streamers) if str(x.channel_id) == str(channel_id)
        )
    except StopIteration:
        return -1


def float_round(number, ndigits=2):
    return round(float(number), ndigits)


def server_time(message_data):
    return (
        datetime.fromtimestamp(
            message_data["server_time"], timezone.utc
        ).isoformat()
        + "Z"
        if message_data is not None and "server_time" in message_data
        else datetime.fromtimestamp(time.time(), timezone.utc).isoformat() + "Z"
    )


# https://en.wikipedia.org/wiki/Cryptographic_nonce
def create_nonce(length=30) -> str:
    nonce = ""
    for i in range(length):
        char_index = randrange(0, 10 + 26 + 26)
        if char_index < 10:
            char = chr(ord("0") + char_index)
        elif char_index < 10 + 26:
            char = chr(ord("a") + char_index - 10)
        else:
            char = chr(ord("A") + char_index - 26 - 10)
        nonce += char
    return nonce


# for mobile-token


def get_user_agent(browser: str) -> str:
    """try:
        return USER_AGENTS[platform.system()][browser]
    except KeyError:
        # return USER_AGENTS["Linux"]["FIREFOX"]
        # return USER_AGENTS["Windows"]["CHROME"]"""
    return USER_AGENTS["Android"]["TV"]
    # return USER_AGENTS["Android"]["App"]


def remove_emoji(string: str) -> str:
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002500-\U00002587"  # chinese char
        "\U00002589-\U00002BEF"  # I need Unicode Character “█” (U+2588)
        "\U00002702-\U000027B0"
        "\U00002702-\U000027B0"
        "\U000024C2-\U00002587"
        "\U00002589-\U0001F251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u2640-\u2642"
        "\u2600-\u2B55"
        "\u200d"
        "\u23cf"
        "\u23e9"
        "\u231a"
        "\ufe0f"  # dingbats
        "\u3030"
        "\u231b"
        "\u2328"
        "\u23cf"
        "\u23e9"
        "\u23ea"
        "\u23eb"
        "\u23ec"
        "\u23ed"
        "\u23ee"
        "\u23ef"
        "\u23f0"
        "\u23f1"
        "\u23f2"
        "\u23f3"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub(r"", string)


def at_least_one_value_in_settings_is(items, attr, value=True):
    for item in items:
        if getattr(item.settings, attr) == value:
            return True
    return False


def copy_values_if_none(settings, defaults):
    values = list(
        filter(
            lambda x: x.startswith("__") is False
                      and callable(getattr(settings, x)) is False,
            dir(settings),
        )
    )

    for value in values:
        if getattr(settings, value) is None:
            setattr(settings, value, getattr(defaults, value))
    return settings


def set_default_settings(settings, defaults):
    # If no settings was provided use the default settings ...
    # If settings was provided but maybe are only partial set
    # Get the default values from Settings.streamer_settings
    return (
        deepcopy(defaults)
        if settings is None
        else copy_values_if_none(settings, defaults)
    )


'''def char_decision_as_index(char):
    return 0 if char == "A" else 1'''


def internet_connection_available(host="8.8.8.8", port=53, timeout=3):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error:
        return False


def percentage(a, b):
    return 0 if a == 0 else int((a / b) * 100)


def create_chunks(lst, n):
    return [lst[i: (i + n)] for i in range(0, len(lst), n)]  # noqa: E203


def download_file(name, fpath):
    r = requests.get(
        path.join(GITHUB_url, name),
        headers={"User-Agent": get_user_agent("FIREFOX")},
        stream=True,
    )
    if r.status_code == 200:
        with open(fpath, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
    return True


def read(fname):
    return open(path.join(path.dirname(__file__), fname), encoding="utf-8").read()


def init2dict(content):
    return dict(re.findall(r"""__([a-z]+)__ = "([^"]+)""", content))


def check_versions():
    try:
        current_version = init2dict(read("__init__.py"))
        current_version = (
            current_version["version"] if "version" in current_version else "0.0.0"
        )
    except Exception:
        current_version = "0.0.0"
    try:
        r = requests.get(
            "/".join(
                [
                    s.strip("/")
                    for s in [GITHUB_url, "TwitchChannelPointsMiner", "__init__.py"]
                ]
            )
        )
        github_version = init2dict(r.text)
        github_version = (
            github_version["version"] if "version" in github_version else "0.0.0"
        )
    except Exception:
        github_version = "0.0.0"
    return current_version, github_version


_alphabet_base_36 = '0123456789abcdefghijklmnopqrstuvwxyz'


def create_random_id(length: int) -> str:
    """
    Creates a random string of given length.
    Mimics the ID generation function Twitch uses in their WebSocket request IDs.
    :param length: The length of the string to create.
    :return: The generated string.
    """

    def mapping(value: int):
        value &= 63
        if value < 36:
            return _alphabet_base_36[value]
        elif value < 62:
            return _alphabet_base_36[value - 26].upper()
        elif value > 62:
            return "-"
        else:
            return "_"

    return "".join(map(mapping, secrets.token_bytes(length)))


def simple_repr(obj) -> str:
    """
    Creates a simple representation of a given object.
    :param obj: The object to represent.
    :return: The string representation of the object.
    """
    if obj is None:
        return "None"
    return f"<{obj.__class__.__name__}: {obj.__dict__}>"


T = TypeVar("T")


def combine(*iterables: Iterable[T]) -> Iterable[T]:
    """
    Combines multiple iterables into one.
    :param iterables: The iterables to combine.
    :return: The resulting iterable.
    """
    for iterable in iterables:
        yield from iterable


def format_timestamp(timestamp: datetime) -> str:
    """
    Formats a datetime object in ISO 8601 format for interoperability with the Twitch Web client.
    Specifically, datetimes will be formatted like "2025-10-03T07:36:29.045Z"

    :param timestamp: The datetime object to format.
    :return: The formatted datetime string.
    """
    return f"{timestamp:%Y-%m-%dT%H:%M:%S}.{timestamp.microsecond // 1000:03d}Z"

