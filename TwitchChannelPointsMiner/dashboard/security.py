"""Allowlisted dashboard output and bounded, credential-redacted diagnostics."""

import re

_URL_SECRET = re.compile(
    r"https?://(?:[^\s/]+\.)?discord(?:app)?\.com/api/webhooks/[^\s\"'<>]+", re.I
)
_AUTH = re.compile(r"(?i)(?:oauth:|bearer\s+|oauth\s+)[A-Za-z0-9._~-]+")
_SECRET = re.compile(
    r"""(?ix)(["']?(?:auth[-_]?token|access[-_]?token|refresh[-_]?token|token|sig|signature|client[-_]?secret|authorization|password|cookie|set-cookie|client-integrity|webhook_api)["']?\s*[:=]\s*)(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s,;}]+)"""
)
_QUERY = re.compile(r"(?i)([?&](?:token|sig|signature|auth|key)=)[^&\s\"']+")
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def redact(value):
    value = _ANSI.sub("", str(value))
    value = re.sub(
        r"(?im)(\b(?:Cookie|Set-Cookie|Authorization):\s*)[^\r\n]+",
        lambda m: m[1] + "[redacted]",
        value,
    )
    value = _URL_SECRET.sub("[redacted webhook]", value)
    value = _AUTH.sub("[redacted credential]", value)
    value = _SECRET.sub(lambda m: m[1] + '"[redacted]"', value)
    return _QUERY.sub(lambda m: m[1] + "[redacted]", value)
