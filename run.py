# -*- coding: utf-8 -*-
from colorama import Fore
from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.classes.Chat import ChatPresence
from TwitchChannelPointsMiner.classes.Discord import Discord
from TwitchChannelPointsMiner.classes.Settings import Priority, Events, FollowersOrder
from TwitchChannelPointsMiner.classes.Telegram import Telegram
from TwitchChannelPointsMiner.classes.entities.Bet import Strategy, BetSettings, Condition, OutcomeKeys, \
    FilterCondition, DelayMode
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings
from TwitchChannelPointsMiner.logger import LoggerSettings, ColorPalette

import keep_alive,logging,os
keep_alive.keep_alive()

user = os.getenv('User')
password = os.getenv('Password')
webHook = os.getenv('WebHook')
chatID = os.getenv('ChatID')
telegramToken = os.getenv('TelegramToken')

twitch_miner = TwitchChannelPointsMiner(
    username=user,
    password=password,  
    claim_drops_startup=True,  
    priority=[  
        Priority.STREAK,  
        Priority.DROPS,   
        Priority.ORDER  
    ],

    enable_analytics=True,
    logger_settings=LoggerSettings(
        save=True,  
        console_level=logging.INFO,
        console_username=False,
        file_level=logging.INFO,
        emoji=False,  
        less=True,  
        colored=False,  
        color_palette=ColorPalette(  
            STREAMER_ONLINE=Fore.GREEN,  
            STREAMER_OFFLINE=Fore.RED,
            GAIN_FOR_RAID=Fore.YELLOW,
            GAIN_FOR_CLAIM=Fore.YELLOW,
            GAIN_FOR_WATCH=Fore.WHITE,
            GAIN_FOR_WATCH_STREAK=Fore.MAGENTA,
            BET_WIN=Fore.GREEN,
            BET_LOSE=Fore.RED,
            BET_REFUND=Fore.RESET,
            BET_FILTERS=Fore.MAGENTA,
            BET_GENERAL=Fore.BLUE,
            BET_FAILED=Fore.RED,
        ),
        telegram=Telegram(  
            chat_id=chatID,
            token=telegramToken,
            events=[
                Events.STREAMER_ONLINE,
                Events.STREAMER_OFFLINE,
                Events.BONUS_CLAIM,
                Events.DROP_CLAIM,
                Events.DROP_STATUS,
                Events.GAIN_FOR_RAID,
                Events.GAIN_FOR_CLAIM,
                Events.GAIN_FOR_WATCH,
                Events.CHAT_MENTION
            ], 
            disable_notification=True,
        ),
        discord=Discord(
            webhook_api=webHook,
            events=[
                Events.STREAMER_ONLINE,
                Events.STREAMER_OFFLINE,
                Events.BONUS_CLAIM,
                Events.DROP_CLAIM,
                Events.DROP_STATUS,
                Events.GAIN_FOR_RAID,
                Events.GAIN_FOR_CLAIM,
                Events.GAIN_FOR_WATCH,
                Events.CHAT_MENTION
            ],
        )
    ),
    streamer_settings=StreamerSettings(
        make_predictions=False,
        follow_raid=False,
        claim_drops=True,
        watch_streak=True,
        chat=ChatPresence.ONLINE,
        bet=BetSettings(
            strategy=Strategy.SMART, 
            percentage=5,  
            percentage_gap=20,  
            max_points=50000, 
            stealth_mode=True,
            delay_mode=DelayMode.FROM_END,
            delay=6,
            minimum_points=20000,
            filter_condition=FilterCondition(
                by=OutcomeKeys.TOTAL_USERS,
                where=Condition.LTE,
                value=800
            )
        )
    )
)

twitch_miner.analytics(host="0.0.0.0", port=5050, refresh=36000, days_ago=30)  # Start the Analytics web-server


twitch_miner.mine(
    [     
        Streamer("ralumyst"),
        Streamer ("xhenniii", settings=StreamerSettings(chat=ChatPresence.ONLINE)),
        Streamer("cypathic"),
        Streamer("ggxenia"),
        Streamer("Faellu"),
        Streamer("kittxnlylol"),
        Streamer("lauraa"),
        Streamer("melvniely"), 
        Streamer("adorbie"),
        Streamer("alisa"),
        Streamer("chloelock"),
        Streamer("daeye"), 
        Streamer("dessyy"),
        Streamer("etain"),
        Streamer("Ellie_m_"),
        Streamer("hannahmelin"),
        Streamer("hekimae"),
        Streamer("ibbaa"), 
        Streamer("imSoff"),
        Streamer("itspinkwater"),
        Streamer("justcallmemary"),
        Streamer("karmixxy"),
        Streamer("kiaa"), 
        Streamer("ki_pi"),
        Streamer("laurenp681"),
        Streamer("lillithy"),
        Streamer("maawlin"),
        Streamer("manyissues"), 
        Streamer("marteemilie"),
        Streamer("martey0"),
        Streamer("maryydlg"),
        Streamer("mathy"),
        Streamer("midoriopup"),
        Streamer("nemuri_bun"),
        Streamer("punzzl"),
        Streamer("rainingshady"),
        Streamer("rikkemor"),
        Streamer("shabs"),
        Streamer("smoodie"), 
        Streamer("strawberrytops"),
        Streamer("suzie95"),
        Streamer("suzikynz"),
        Streamer("Witch_Sama")

    ],
    followers=False,  
    followers_order=FollowersOrder.ASC
)
