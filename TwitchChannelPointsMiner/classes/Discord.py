from textwrap import dedent
import requests
import re
from TwitchChannelPointsMiner.classes.Settings import Events

def get_streamer_icon(username):
    response = requests.get(f"https://www.twitch.tv/{username}")
    match = re.search(r'meta property="og:image" content="(.*?)"', response.text)
    if match:
        return match.group(1)
    return None


class Discord:
    __slots__ = ["webhook_api", "events"]

    def __init__(self, webhook_api: str, events: list):
        self.webhook_api = webhook_api
        self.events = [str(e) for e in events]

    def send(self, message: str, event: Events) -> None:
        #print(message)
        if str(event) in self.events:
            if ") is Online!" in message:
                username_section = message.split('username=')[1]
                username = username_section.split(',')[0]
                channel_points_section = message.split('channel_points=')[1]
                channel_points = channel_points_section.split(')')[0]
                twitch_url = f"https://twitch.tv/{username}"
                icon_url = get_streamer_icon(username)

                embed_message = {
                    "username": "Twitch Channel Points Miner",
                    "avatar_url": "https://i.imgur.com/X9fEkhT.png",
                    "embeds": [
                        {
                            "title": f"{username} - is Online!",
                            "url": twitch_url,
                            "description": "Current stats",
                            "color": 5763719,
                            "fields": [
                                {
                                    "name": "Channel Points",
                                    "value": channel_points,
                                    "inline": False
                                }
                            ],
                            "thumbnail": {
                                "url": icon_url
                            }
                        }
                    ]
                }

                requests.post(
                    url=self.webhook_api,
                    json=embed_message,
                )
            
            elif ") is Offline!" in message:
                username_section = message.split('username=')[1]
                username = username_section.split(',')[0]
                channel_points_section = message.split('channel_points=')[1]
                channel_points = channel_points_section.split(')')[0]
                twitch_url = f"https://twitch.tv/{username}"
                icon_url = get_streamer_icon(username)

                embed_message = {
                    "username": "Twitch Channel Points Miner",
                    "avatar_url": "https://i.imgur.com/X9fEkhT.png",
                    "embeds": [
                        {
                            "title": f"{username} - is Offline!",
                            "url": twitch_url,
                            "description": "Current stats",
                            "color": 15548997,
                            "fields": [
                                {
                                    "name": "Channel Points",
                                    "value": channel_points,
                                    "inline": False
                                }
                            ],
                            "thumbnail": {
                                "url": icon_url
                            }
                        }
                    ]
                }

                requests.post(
                    url=self.webhook_api,
                    json=embed_message,
                )
                
            elif ") - Reason: " in message:
                reason_section = message.split(') - Reason: ')[1]
                match = re.search(r'[+]\d+', message)
                reason_number = match.group(0) if match else ""


                channel_points_section = message.split('channel_points=')[1]
                channel_points = channel_points_section.split(')')[0]
                username_section = message.split('username=')[1]
                username = username_section.split(',')[0]
                twitch_url = f"https://twitch.tv/{username}"
                icon_url = get_streamer_icon(username)

                embed_message = {
                    "username": "Twitch Channel Points Miner",
                    "avatar_url": "https://i.imgur.com/X9fEkhT.png",
                    "embeds": [
                        {
                            "title": f"{username} - Update",
                            "url": twitch_url,
                            #"description": "Aktuelle Stats",
                            "color": 15844367,
                            "fields": [
                                {
                                    "name": "New Stats",
                                    "value": channel_points,
                                    "inline": False
                                },
                                {
                                    "name": f"Reason: {reason_section}",
                                    "value": reason_number,
                                    "inline": False
                                }
                            ],
                            "thumbnail": {
                                "url": icon_url
                            }
                        }
                    ]
                }

                requests.post(
                    url=self.webhook_api,
                    json=embed_message,
                )
            elif ") - Result: WIN" in message:
                match = re.search(r'Gained: \+(\d+(?:[.,]\d+)?k?)', message)
                result = match.group(1) if match else ""

                channel_points_section = message.split('channel_points=')[1]
                channel_points = channel_points_section.split(')')[0]
                username_section = message.split('username=')[1]
                username = username_section.split(',')[0]
                twitch_url = f"https://twitch.tv/{username}"
                icon_url = get_streamer_icon(username)

                embed_message = {
                    "username": "Twitch Channel Points Miner",
                    "avatar_url": "https://i.imgur.com/X9fEkhT.png",
                    "embeds": [
                        {
                            "title": f"{username} - Update",
                            "url": twitch_url,
                            #"description": "Aktuelle Stats",
                            "color": 5763719,
                            "fields": [
                                {
                                    "name": "Prediction won:",
                                    "value": f"Plus from: {result}",
                                    "inline": False
                                },
                                {
                                    "name": "New Stats",
                                    "value": channel_points,
                                    "inline": False
                                }
                            ],
                            "thumbnail": {
                                "url": icon_url
                            }
                        }
                    ]
                }

                requests.post(
                    url=self.webhook_api,
                    json=embed_message,
                )
            elif ") - Result: LOSE" in message:
                match = re.search(r'Lost: \-(\d+(?:[.,]\d+)?k?)', message)
                result = match.group(1) if match else ""

                channel_points_section = message.split('channel_points=')[1]
                channel_points = channel_points_section.split(')')[0]
                username_section = message.split('username=')[1]
                username = username_section.split(',')[0]
                twitch_url = f"https://twitch.tv/{username}"
                icon_url = get_streamer_icon(username)

                embed_message = {
                    "username": "Twitch Channel Points Miner",
                    "avatar_url": "https://i.imgur.com/X9fEkhT.png",
                    "embeds": [
                        {
                            "title": f"{username} - Update",
                            "url": twitch_url,
                            #"description": "Aktuelle Stats",
                            "color": 15548997,
                            "fields": [
                                {
                                    "name": "Prediction Lost:",
                                    "value": f"Minus frome: {result}",
                                    "inline": False
                                },
                                {
                                    "name": "New Stats",
                                    "value": channel_points,
                                    "inline": False
                                }
                            ],
                            "thumbnail": {
                                "url": icon_url
                            }
                        }
                    ]
                }

                requests.post(
                    url=self.webhook_api,
                    json=embed_message,
                )

            else:
                requests.post(
                    url=self.webhook_api,
                    data={
                        "content": dedent(message),
                        "username": "Twitch Channel Points Miner",
                        "avatar_url": "https://i.imgur.com/X9fEkhT.png",
                    },
                )