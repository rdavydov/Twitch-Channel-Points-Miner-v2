# Twitch endpoints
URL = "https://www.twitch.tv"               # Browser, Apps
# URL = "https://m.twitch.tv"               # Mobile Browser
# URL = "https://android.tv.twitch.tv"      # TV
IRC = "irc.chat.twitch.tv"
IRC_PORT = 6667
WEBSOCKET = "wss://pubsub-edge.twitch.tv/v1"
CLIENT_ID = "ue6666qo983tsx6so1t0vnawi233wa"        # TV
# CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"      # Browser
# CLIENT_ID = "r8s4dac0uhzifbpu9sjdiwzctle17ff"     # Mobile Browser
# CLIENT_ID = "kd1unb4b3q4t58fwlpcbzcbnm76a8fp"     # Android App
# CLIENT_ID = "851cqzxpb9bqu9z6galo155du"           # iOS App
DROP_ID = "c2542d6d-cd10-4532-919b-3d19f30a768b"
# CLIENT_VERSION = "32d439b2-bd5b-4e35-b82a-fae10b04da70"  # Android App
CLIENT_VERSION = "ef928475-9403-42f2-8a34-55784bd08e16"  # Browser

USER_AGENTS = {
    "Windows": {
        'CHROME': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
        "FIREFOX": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0",
    },
    "Linux": {
        "CHROME": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.96 Safari/537.36",
        "FIREFOX": "Mozilla/5.0 (X11; Linux x86_64; rv:85.0) Gecko/20100101 Firefox/85.0",
    },
    "Android": {
        # "App": "Dalvik/2.1.0 (Linux; U; Android 7.1.2; SM-G975N Build/N2G48C) tv.twitch.android.app/13.4.1/1304010"
        "App": "Dalvik/2.1.0 (Linux; U; Android 7.1.2; SM-G977N Build/LMY48Z) tv.twitch.android.app/14.3.2/1403020",
        "TV": "Mozilla/5.0 (Linux; Android 7.1; Smart Box C1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
    }
}

BRANCH = "master"
GITHUB_url = (
    "https://raw.githubusercontent.com/rdavydov/Twitch-Channel-Points-Miner-v2/"
    + BRANCH
)


class GQLOperations:
    url = "https://gql.twitch.tv/gql"
    integrity_url = "https://gql.twitch.tv/integrity"
    WithIsStreamLiveQuery = {
        "operationName": "WithIsStreamLiveQuery",
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "04e46329a6786ff3a81c01c50bfa5d725902507a0deb83b0edbf7abe7a3716ea",
            }
        },
    }
    PlaybackAccessToken = {
        "operationName": "PlaybackAccessToken",
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "ed230aa1e33e07eebb8928504583da78a5173989fadfb1ac94be06a04f3cdbe9",
            }
        },
    }
    VideoPlayerStreamInfoOverlayChannel = {
        "operationName": "VideoPlayerStreamInfoOverlayChannel",
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "198492e0857f6aedead9665c81c5a06d67b25b58034649687124083ff288597d",
            }
        },
    }
    ClaimCommunityPoints = {
        "operationName": "ClaimCommunityPoints",
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "46aaeebe02c99afdf4fc97c7c0cba964124bf6b0af229395f1f6d1feed05b3d0",
            }
        },
    }
    CommunityMomentCallout_Claim = {
        "operationName": "CommunityMomentCallout_Claim",
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "e2d67415aead910f7f9ceb45a77b750a1e1d9622c936d832328a0689e054db62",
            }
        },
    }
    DropsPage_ClaimDropRewards = {
        "operationName": "DropsPage_ClaimDropRewards",
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "a455deea71bdc9015b78eb49f4acfbce8baa7ccbedd28e549bb025bd0f751930",
            }
        },
    }
    ChannelPointsContext = {
        "operationName": "ChannelPointsContext",
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "7fe050e3761eb2cf258d70ee1a21cbd76fa8cf3d7e7b12fc437e7029d446b5e3",
            }
        },
    }
    JoinRaid = {
        "operationName": "JoinRaid",
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "c6a332a86d1087fbbb1a8623aa01bd1313d2386e7c63be60fdb2d1901f01a4ae",
            }
        },
    }
    ModViewChannelQuery = {
        "operationName": "ModViewChannelQuery",
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "df5d55b6401389afb12d3017c9b2cf1237164220c8ef4ed754eae8188068a807",
            }
        },
    }
    Inventory = {
        "operationName": "Inventory",
        "variables": {"fetchRewardCampaigns": False},
        # "variables": {},
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "8337eb8541b314040b0edde0c09c5c7a2783ba1960aa9edfbf3bac16d0fec404",
            }
        },
    }
    MakePrediction = {
        "operationName": "MakePrediction",
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "b44682ecc88358817009f20e69d75081b1e58825bb40aa53d5dbadcc17c881d8",
            }
        },
    }
    ViewerDropsDashboard = {
        "operationName": "ViewerDropsDashboard",
        # "variables": {},
        "variables": {"fetchRewardCampaigns": False},
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "c16bb890cc8ce7647a96ee69cd313d423a378a3dedadf630a1017cde18975feb",
            }
        },
    }
    DropCampaignDetails = {
        "operationName": "DropCampaignDetails",
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "039277bf98f3130929262cc7c6efd9c141ca3749cb6dca442fc8ead9a53f77c1",
            }
        },
    }
    DropsHighlightService_AvailableDrops = {
        "operationName": "DropsHighlightService_AvailableDrops",
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "782dad0f032942260171d2d80a654f88bdd0c5a9dddc392e9bc92218a0f42d20",
            }
        },
    }
    GetIDFromLogin = {
        "operationName": "GetIDFromLogin",
        "variables": {"login": None},
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "94e82a7b1e3c21e186daa73ee2afc4b8f23bade1fbbff6fe8ac133f50a2f58ca",
            }
        },
    }
    PersonalSections = (
        {
            "operationName": "PersonalSections",
            "variables": {
                "input": {
                    "sectionInputs": ["FOLLOWED_SECTION"],
                    "recommendationContext": {"platform": "web"},
                },
                "channelLogin": None,
                "withChannelUser": False,
                "creatorAnniversariesExperimentEnabled": False,
            },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "9fbdfb00156f754c26bde81eb47436dee146655c92682328457037da1a48ed39",
                }
            },
        },
    )
    ChannelFollows = {
        "operationName": "ChannelFollows",
        "variables": {"limit": 100, "order": "ASC"},
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "eecf815273d3d949e5cf0085cc5084cd8a1b5b7b6f7990cf43cb0beadf546907",
            }
        },
    }
    UserPointsContribution = {
        "operationName": "UserPointsContribution",
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "23ff2c2d60708379131178742327ead913b93b1bd6f665517a6d9085b73f661f"
            }
        }
    }
    ContributeCommunityPointsCommunityGoal = {
        "operationName": "ContributeCommunityPointsCommunityGoal",
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "5774f0ea5d89587d73021a2e03c3c44777d903840c608754a1be519f51e37bb6"
            }
        }
    }
    # Raw query text used when a persisted query hash is rejected
    # (PersistedQueryNotFound). Twitch ignores unused variables.
    raw_queries = {
        "DropsPage_ClaimDropRewards": "mutation DropsPage_ClaimDropRewards($input: ClaimDropRewardsInput!) { claimDropRewards(input: $input) { status } }",
        "Inventory": "query Inventory { currentUser { inventory { dropCampaignsInProgress { id name status startAt endAt self { isAccountConnected } game { id name displayName } timeBasedDrops { id name requiredMinutesWatched startAt endAt benefitEdges { benefit { id name } } self { dropInstanceID isClaimed currentMinutesWatched hasPreconditionsMet } } } } } }",
        "ViewerDropsDashboard": "query ViewerDropsDashboard { currentUser { dropCampaigns { id name status startAt endAt game { id name displayName } } } }",
        "DropCampaignDetails": "query DropCampaignDetails($dropID: ID!, $channelLogin: ID!) { user(id: $channelLogin) { id dropCampaign(id: $dropID) { id name status startAt endAt game { id name displayName } allow { channels { id name } } timeBasedDrops { id name requiredMinutesWatched startAt endAt benefitEdges { benefit { id name } } } } } }",
        "DropsHighlightService_AvailableDrops": "query DropsHighlightService_AvailableDrops($channelID: ID!) { channel(id: $channelID) { id viewerDropCampaigns { id name } } }",
        "ModViewChannelQuery": "query ModViewChannelQuery($channelLogin: String!) { user(login: $channelLogin) { id self { isModerator } } }",
    }
