"""Normalize allowlisted Twitch reads without invoking miner actions."""

import copy
from datetime import datetime

from TwitchChannelPointsMiner.classes.entities.Rewards import (
    StreakRecovery,
    WeeklyRewards,
)
from TwitchChannelPointsMiner.constants import GQLOperations


def timestamp(value):
    if isinstance(value, (int, float)):
        return value
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError, AttributeError):
        return None


def operation(name, variables=None):
    payload = copy.deepcopy(getattr(GQLOperations, name))
    payload.setdefault("variables", {}).update(variables or {})
    return payload


def normalize(name, response):
    if (
        name == "WeeklyVisitRewardsQuery"
        and isinstance(response, dict)
        and response.get("errors")
        and all(
            isinstance(e, dict)
            and e.get("message")
            == 'graphql: got nil for non-null "WeeklyVisitRewardTier"'
            and e.get("path")
            == ["channel", "self", "weeklyVisitRewards", "currentReward"]
            for e in response["errors"]
        )
    ):
        return {"weekly": None}
    data = response.get("data")
    if not isinstance(data, dict) or response.get("errors"):
        raise ValueError("Twitch did not return a complete response")
    if name == "ChannelPointsContext":
        channel = (data.get("community") or {}).get("channel")
        if not isinstance(channel, dict):
            raise ValueError("Channel context unavailable")
        own = channel.get("self") or {}
        points = own.get("communityPoints") or {}
        settings = channel.get("communityPointsSettings") or {}
        value = points.get("balance")
        return {
            "points": value
            if isinstance(value, int) and not isinstance(value, bool)
            else None,
            "points_enabled": settings.get("isEnabled"),
            "subscription_tier": (own.get("subscriptionBenefit") or {}).get("tier"),
        }
    if name == "VideoPlayerStreamInfoOverlayChannel":
        user = data.get("user")
        if not isinstance(user, dict) or "stream" not in user:
            raise ValueError("Stream status unavailable")
        stream = user.get("stream")
        settings = (
            user.get("broadcastSettings")
            or (stream or {}).get("broadcastSettings")
            or {}
        )
        return {
            "online": stream is not None,
            "broadcast_id": (stream or {}).get("id"),
            "title": settings.get("title"),
            "game": (settings.get("game") or {}).get("displayName")
            or (settings.get("game") or {}).get("name"),
            "viewers": (stream or {}).get("viewersCount"),
            "stream_started_at": timestamp((stream or {}).get("createdAt")),
        }
    if name == "RewardList":
        own = (data.get("channel") or {}).get("self") or {}
        if "watchStreakMilestone" not in own:
            raise ValueError("Streak state unavailable")
        milestone = own.get("watchStreakMilestone")
        recovery = StreakRecovery.from_dict(milestone)
        viewer = (milestone or {}).get("watchStreakMilestone") or {}
        days = viewer.get("value")
        return {
            "streak": recovery.streak_days
            if recovery is not None
            else int(days)
            if isinstance(days, str) and days.isdigit()
            else days
            if isinstance(days, int) and not isinstance(days, bool)
            else None,
            "streak_achieved_at": timestamp(viewer.get("achievementTimestamp")),
            "recovery": None
            if recovery is None
            else dict(
                days=recovery.streak_days,
                expires_at=recovery.expires_at,
                missed_broadcasts=sorted(recovery.missed_broadcasts),
                recoverable=recovery.recoverable(),
            ),
        }
    if name == "WeeklyVisitRewardsQuery":
        own = (data.get("channel") or {}).get("self") or {}
        if "weeklyVisitRewards" not in own:
            raise ValueError("Weekly rewards unavailable")
        rewards = WeeklyRewards.from_dict(own.get("weeklyVisitRewards"))
        if own["weeklyVisitRewards"] is not None and rewards is None:
            raise ValueError("Weekly rewards response incomplete")
        return {
            "weekly": None
            if rewards is None
            else dict(
                event_id=rewards.event_id,
                ends_at=rewards.ends_at,
                days_visited=rewards.days_visited,
                accumulated_weeks=rewards.accumulated_weeks,
                reward_count=rewards.reward_count,
                visited_today=rewards.visited_today,
                earned_this_week=rewards.earned_this_week,
            )
        }
    if name == "ChatRoomBanStatus":
        if "chatRoomBanStatus" not in data:
            raise ValueError("Chat ban status unavailable")

        def banned(status):
            if isinstance(status, dict):
                if "banStatus" in status:
                    return banned(status["banStatus"])
                if "isBanned" in status:
                    return bool(status["isBanned"])
                return any(
                    k in status
                    for k in (
                        "bannedUser",
                        "createdAt",
                        "expiresAt",
                        "expiresInMs",
                        "isPermanent",
                        "moderator",
                        "reason",
                        "roomOwner",
                    )
                )
            return bool(status)

        return {"chat_banned": banned(data["chatRoomBanStatus"])}
    if name == "ChannelFollows":
        follows = (data.get("user") or {}).get("follows")
        if not isinstance(follows, dict):
            raise ValueError("Follow dates unavailable")
        return {
            "follow_dates": {
                e["node"]["login"]
                .lower(): ((e["node"].get("self") or {}).get("follower") or {})
                .get("followedAt")
                for e in follows.get("edges", [])
                if isinstance(e.get("node"), dict) and e["node"].get("login")
            },
            "has_next": (follows.get("pageInfo") or {}).get("hasNextPage", False),
            "cursor": (follows.get("edges") or [{}])[-1].get("cursor"),
        }
    if name == "Inventory":
        inventory = (data.get("currentUser") or {}).get("inventory")
        if not isinstance(inventory, dict):
            raise ValueError("Drop inventory unavailable")
        return {"drops": inventory_drops(inventory)}
    if name == "ViewerDropsDashboard":
        own = data.get("currentUser")
        if not isinstance(own, dict) or "dropCampaigns" not in own:
            raise ValueError("Drop campaigns unavailable")
        campaigns = own["dropCampaigns"]
        if campaigns is None:
            campaigns = []
        if not isinstance(campaigns, list):
            raise ValueError("Drop campaigns response incomplete")
        # Twitch now also supplies event-based reward campaigns at the root.
        rewards = data.get("rewardCampaignsAvailableToUser")
        if isinstance(rewards, list):
            campaigns = campaigns + rewards
        return {
            "campaigns": [campaign_summary(c) for c in campaigns if isinstance(c, dict)]
        }
    if name == "DropCampaignDetails":
        campaign = (data.get("user") or {}).get("dropCampaign")
        if not isinstance(campaign, dict):
            raise ValueError("Campaign details unavailable")
        return {
            "campaign": campaign_summary(campaign),
            "drops": inventory_drops({"dropCampaignsInProgress": [campaign]}),
        }
    return {}


def campaign_summary(campaign):
    return {
        "id": campaign.get("id"),
        "name": campaign.get("name"),
        "game": (campaign.get("game") or {}).get("displayName")
        or (campaign.get("game") or {}).get("name"),
        "status": campaign.get("status"),
        "starts_at": timestamp(campaign.get("startAt") or campaign.get("startsAt")),
        "ends_at": timestamp(campaign.get("endAt") or campaign.get("endsAt")),
    }


def inventory_drops(inventory):
    rows = []
    for campaign in inventory.get("dropCampaignsInProgress") or []:
        base = campaign_summary(campaign)
        for drop in campaign.get("timeBasedDrops") or []:
            own = drop.get("self") or {}
            rows.append(
                {
                    "id": drop.get("id"),
                    "campaign_id": base["id"],
                    "campaign": base["name"],
                    "game": base["game"],
                    "name": drop.get("name"),
                    "reward": ", ".join(
                        (e.get("benefit") or {}).get("name", "")
                        for e in drop.get("benefitEdges") or []
                    ),
                    "minutes": own.get("currentMinutesWatched"),
                    "required_minutes": drop.get("requiredMinutesWatched"),
                    "claimed": own.get("isClaimed"),
                    "preconditions_met": own.get("hasPreconditionsMet"),
                    "ends_at": timestamp(drop.get("endAt")) or base["ends_at"],
                }
            )
    for reward in inventory.get("gameEventDrops") or []:
        # Inventory confirms these historical rewards, even when their campaign has ended.
        rows.append(
            {
                "id": reward.get("id"),
                "campaign_id": None,
                "campaign": "Claimed reward",
                "game": (reward.get("game") or {}).get("displayName"),
                "name": reward.get("name"),
                "reward": reward.get("name"),
                "claimed": True,
                "claimed_at": timestamp(reward.get("lastAwardedAt")),
            }
        )
    return rows
