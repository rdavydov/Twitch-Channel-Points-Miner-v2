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
StreamerList = [
        ("ralumyst"),
        ("cypathic"),
        ("kittxnlylol"),
        ("lauraa"),
        ("melvniely"), 
        ("adorbie"),
        ("alisa"),
        ("chloelock"),
        ("daeye"), 
        ("dessyy"),
        ("etain"),
        ("hannahmelin"),
        ("hekimae"),
        ("ibbaa"), 
        ("imSoff"),
        ("itspinkwater"),
        ("justcallmemary"),
        ("karmixxy"),
        ("kiaa"), 
        ("ki_pi"),
        ("laurenp681"),
        ("lillithy"),
        ("maawlin"),
        ("manyissues"), 
        ("marteemilie"),
        ("martey0"),
        ("maryydlg"),
        ("mathy"),
        ("midoriopup"),
        ("punzzl"),
        ("rainingshady"),
        ("rikkemor"),
        ("shabs"),
        ("smoodie"), 
        ("strawberrytops"),
        ("suzie95"),
        ("suzikynz"),
        ("Witch_Sama")
    ]

twitch_miner = TwitchChannelPointsMiner(
    username=user,
    password=password,  
    claim_drops_startup=True,  
    priority=[  
        Priority.STREAK,  
        Priority.DROPS,   
        Priority.ORDER  
    ],

    enable_analytics=False,
    logger_settings=LoggerSettings(
        save=False,  
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
        Streamer ("xhenniii", settings=StreamerSettings(chat=ChatPresence.ONLINE)),       
        Streamer(StreamerList)
    ],
    followers=False,  
    followers_order=FollowersOrder.ASC
)
