# Twitch Channel Points Miner (Armi1014 Fork)

A **reliability-first fork** of `Twitch-Channel-Points-Miner-v2`.

Built for people who want:
- **better watch streak reliability**
- **cleaner favorite / priority behavior**
- **faster startup in real use**
- **less transient Twitch/API/network log noise**

If upstream mostly works for you but occasionally behaves weirdly, this fork is meant to be the **more practical, more stable version**.
It also aims to be the **faster fork in day-to-day use**, especially during startup and early channel refreshes.

> Not affiliated with Twitch. Use at your own risk.

## Quick Start

If you are coming from upstream, one of the first things you should notice is that this fork is tuned to spend less time stuck in slow startup behavior before it becomes usable.

```sh
git clone https://github.com/Armi1014/Twitch-Channel-Points-Miner-v2
cd Twitch-Channel-Points-Miner-v2
python -m venv .venv
````

**Windows**

```sh
.venv\Scripts\activate
copy example.py run.py
pip install -r requirements.txt
python run.py
```

**Linux / macOS**

```sh
source .venv/bin/activate
cp example.py run.py
pip install -r requirements.txt
python run.py
```

## Why this fork

Compared to upstream, this fork focuses on **reliability first**:

* better handling of transient Twitch/API/network issues
* more reliable watch streak behavior, including already-online channels at startup
* per-account streak cache files to avoid multi-account conflicts
* clearer `Priority.FAVORITE` behavior
* faster startup and less waiting during the initial refresh cycle
* reduced recurring timeout / backend error log spam

**Example startup improvement**

* upstream sample: `179s`
* this fork sample: `14s`
* about **12.8x faster** in that test

Results vary depending on account size, network quality, and Twitch backend health.
The exact number will vary, but faster startup is a core goal of this fork, not just a side effect.

## Use this fork if...

* you care more about **reliability** than staying as close as possible to upstream
* you use **watch streaks** heavily
* you want clearer favorite / priority behavior
* you want the miner to become usable faster after launch
* you want fewer annoying transient error logs

## Subscription Notifications

This fork can send `Events.SUBSCRIPTION` notifications to Discord or other webhook-style integrations.

What it does:

* listens for Twitch IRC `USERNOTICE` events
* formats a cleaner subscription message with the streamer/channel and current points
* only alerts for subscription events that are about **your own account**

What counts as "about your own account":

* you subscribe
* you renew a subscription
* you receive a sub gift
* you upgrade a gift or Prime subscription

What it ignores:

* other viewers subscribing
* other viewers renewing
* other viewers receiving gifted subs

Important:

* this depends on IRC chat being enabled for that streamer
* `chat=ChatPresence.NEVER` disables this feature for that channel
* `chat=ChatPresence.ONLINE` is enough

See [example.py](example.py) for a basic Discord webhook configuration example.

## Docs

* [Latest Releases](https://github.com/Armi1014/Twitch-Channel-Points-Miner-v2/releases)
* [Example Config](example.py)
* [Fork Features](FORK_FEATURES.md)
* [FAQ](FAQ.md)
* [Contributing](CONTRIBUTING.md)

## Disclaimer

This project is not affiliated with Twitch.

Use it at your own risk and make sure you understand the platform rules before using automation tools.
