import re
from datetime import datetime, timezone
from textwrap import dedent
from urllib.parse import quote

import requests

from TwitchChannelPointsMiner.classes.Settings import Events

_STYLES = {
    Events.DROP_CLAIM: ("🎁 Drop claimed", 0x5865F2),
    Events.SUBSCRIPTION: ("🎉 Subscription", 0x9146FF),
    Events.BET_WIN: ("✅ Prediction won", 0x57F287),
    Events.BET_LOSE: ("❌ Prediction lost", 0xED4245),
    Events.BET_REFUND: ("↩️ Prediction refunded", 0xFEE75C),
    Events.BET_FAILED: ("⚠️ Prediction failed", 0xE67E22),
    Events.BET_PLACED: ("🎯 Prediction placed", 0x3498DB),
}
_SUBSCRIPTIONS = {
    "sub": "New subscription",
    "resub": "Subscription renewed",
    "subgift": "Gift subscription received",
    "anonsubgift": "Gift subscription received",
    "giftpaidupgrade": "Gift subscription upgraded",
    "anongiftpaidupgrade": "Gift subscription upgraded",
    "primepaidupgrade": "Prime subscription upgraded",
}
_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_MARKDOWN = re.compile(r"([\\`*_~|\[\]()<>])")


def _length(text):
    # Discord's limits must also hold for UTF-16 surrogate pairs (emoji).
    return len(text.encode("utf-16-le")) // 2


def _truncate(text, limit):
    if limit <= 0:
        return ""
    if _length(text) <= limit:
        return text
    return text.encode("utf-16-le")[: (limit - 1) * 2].decode(
        "utf-16-le", errors="ignore"
    ).rstrip("\\") + "…"


def _text(value):
    clean = _ANSI.sub("", str(value)).encode("utf-8", errors="replace").decode("utf-8")
    return _MARKDOWN.sub(r"\\\1", clean)


def _known(value):
    return value is not None and str(value).strip().lower() not in ("", "unknown")


def _points(value, *, signed=False):
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return f"{number:+,} points" if signed else f"{number:,} points"


class Discord(object):
    __slots__ = ["webhook_api", "events", "message_format"]

    def __init__(self, webhook_api: str, events: list, *, message_format="embed"):
        if message_format not in ("embed", "plain"):
            raise ValueError("Discord message_format must be 'embed' or 'plain'")
        self.webhook_api = webhook_api
        self.events = [str(e) for e in events]
        self.message_format = message_format

    def send(self, message: str, event: Events, *, details=None) -> None:
        if str(event) in self.events:
            requests.post(
                url=self.webhook_api,
                json=self.build_payload(message, event, details=details),
                timeout=20,
            ).raise_for_status()

    def build_payload(self, message: str, event: Events, *, details=None):
        """Render a webhook payload without making a network request."""
        message = _ANSI.sub("", dedent(str(message))).strip()
        payload = {
            "username": "Twitch Channel Points Miner",
            "avatar_url": "https://i.imgur.com/X9fEkhT.png",
            "allowed_mentions": {"parse": []},
        }
        if self.message_format == "plain":
            payload["content"] = _truncate(message, 2000) or "Notification"
            return payload

        details = dict(details or {})
        event = Events.get(event)
        title, color = _STYLES.get(event, ("🔔 Notification", 0x9146FF))
        fields = []

        def add(name, value, *, inline=True, markdown=False):
            if _known(value):
                fields.append({
                    "name": name,
                    "value": str(value) if markdown else _text(value),
                    "inline": inline,
                })

        channel = details.get("channel")
        if _known(channel):
            channel_text = _text(channel)
            if re.fullmatch(r"[A-Za-z0-9_]{1,25}", str(channel)):
                channel_text = f"[{channel_text}](https://www.twitch.tv/{quote(str(channel))})"
            add("Channel", channel_text, inline=False, markdown=True)

        if event == Events.DROP_CLAIM:
            add("Drop", details.get("drop_name"), inline=False)
            add("Reward", details.get("reward"), inline=False)
            minutes = details.get("minutes_required")
            if minutes is not None:
                add("Watch time", f"{minutes} minutes")
        elif event == Events.SUBSCRIPTION:
            subscription_type = _SUBSCRIPTIONS.get(details.get("msg_id"))
            if subscription_type:
                title = f"🎉 {subscription_type}"
            add("Type", subscription_type)
            add("Tier", details.get("plan"))
            add("Subscriber", details.get("subscriber"))
            add("Recipient", details.get("recipient"))
            if details.get("msg_id") in ("subgift", "anonsubgift"):
                add("Gifted by", details.get("gifter"))
            add("Months", details.get("months"))
        elif event in (Events.BET_WIN, Events.BET_LOSE, Events.BET_REFUND, Events.BET_FAILED, Events.BET_PLACED):
            add("Prediction", details.get("prediction"), inline=False)
            add("Outcome", details.get("outcome"), inline=False)
            add("Stake", _points(details.get("stake")))
            add("Source", details.get("source"))
            if details.get("recovered"):
                add("Delivery", "Recovered from Twitch", inline=False)
            add("Payout", _points(details.get("payout")))
            net = _points(details.get("net_points"), signed=True)
            if net is not None:
                add("Net result", f"**{net}**", markdown=True)
            add("Reason", details.get("error"), inline=False)

        timestamp = details.get("timestamp")
        try:
            timestamp = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            timestamp = datetime.now(timezone.utc)
        embed = {
            "title": title,
            "color": color,
            "timestamp": timestamp.isoformat(),
            "footer": {"text": "Twitch Channel Points Miner"},
        }
        budget = 6000 - _length(title) - _length(embed["footer"]["text"])
        fitted_fields = []
        for field in fields[:25]:
            field["name"] = _truncate(field["name"], 256)
            available = min(1024, budget - _length(field["name"]))
            if available <= 0:
                break
            field["value"] = _truncate(field["value"], available)
            budget -= _length(field["name"]) + _length(field["value"])
            fitted_fields.append(field)
        if fitted_fields:
            embed["fields"] = fitted_fields
        show_message = (
            not fields
            or event not in _STYLES
            or (event == Events.BET_FAILED and not _known(details.get("error")))
        )
        description = _text(message) if show_message else ""
        if event == Events.DROP_CLAIM:
            description += "\n[Open Drops inventory](https://www.twitch.tv/drops/inventory)"
        if description.strip() and budget > 0:
            embed["description"] = _truncate(description.strip(), min(4096, budget))
        payload["embeds"] = [embed]
        return payload
