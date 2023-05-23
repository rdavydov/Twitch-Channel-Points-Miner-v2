import logging
import time
import random
from enum import Enum, auto
from threading import Thread

from irc.bot import SingleServerIRCBot

from TwitchChannelPointsMiner.constants import IRC, IRC_PORT
from TwitchChannelPointsMiner.classes.Settings import Events

logger = logging.getLogger(__name__)


class ChatPresence(Enum):
    ALWAYS = auto()
    NEVER = auto()
    ONLINE = auto()
    OFFLINE = auto()

    def __str__(self):
        return self.name


class ClientIRC(SingleServerIRCBot):
    def __init__(self, username, token, channel):
        self.token = token
        self.channel = "#" + channel
        self.__active = False

        super(ClientIRC, self).__init__(
            [(IRC, IRC_PORT, f"oauth:{token}")], username, username
        )

    def on_welcome(self, client, event):
        client.join(self.channel)
    

    def start(self):
        self.__active = True
        self._connect()
        while self.__active:
            try:
                self.reactor.process_once(timeout=0.2)
                time.sleep(0.01)
            except Exception as e:
                logger.error(
                    f"Exception raised: {e}. Thread is active: {self.__active}"
                )

    def die(self, msg="Bye, cruel world!"):
        self.connection.disconnect(msg)
        self.__active = False

    """
    def on_join(self, connection, event):
        logger.info(f"Channel Join: {self.channel} Event: {event}", extra={"emoji": ":speech_balloon:"})
    """

    # """
    def on_pubmsg(self, connection, event):
        msg = event.arguments[0]
        # Known message "TwitchLit A wild {Pokemon} appears TwitchLit Catch it using !pokecatch (winners revealed in 90s)"
        nick = event.source.split("!", 1)[0]
        #logger.info(f"{nick} at {self.channel} wrote: {msg}", extra={"emoji": ":speech_balloon:"})
        # also self._realname
        # if msg.startswith(f"@{self._nickname}"):
        if f"@{self._nickname.lower()}" in msg.lower():
            logger.info(f"{nick} at {self.channel} wrote: {msg}", extra={
                        "emoji": ":speech_balloon:", "event": Events.CHAT_MENTION})
 
        """ START POKEMON CODE """
        pokeescape = "escaped. No one caught it. jonasw5Rigged" #Pokemon Escaped
        if pokeescape in msg:
            pokemon = msg.split(" ")[0]        
            # nickname!username@nickname.tmi.twitch.tv
            nick = event.source.split("!", 1)[0]
            time.sleep(random.randrange(5,30))          
            #self.connection.privmsg(self.channel,f"cezzbbRIOT cezzbbRiotA  Damn you {pokemon} cezzbbRiotA cezzbbRIOT")
            logger.info(f"{pokemon} at {self.channel} Excaped  <https://twitch.tv/{self.channel[1:]}>", extra={"emoji": ":basketball:", "event": Events.CHAT_MENTION})

        pokecaught = " has been caught by: " #Pokemon Caught
        if pokecaught in msg:  #Caught by me
            pokemon = msg.split(" ")[0]        
            if self._nickname.lower() in msg:
                # nickname!username@nickname.tmi.twitch.tv
                nick = event.source.split("!", 1)[0]
                time.sleep(random.randrange(5,30))          
                #self.connection.privmsg(self.channel,f"cezzbbHYPE cezzbbHYPE {pokemon} you pretty you are mine now! cezzbbHYPE cezzbbHYPE")
                logger.info(f"Pokemon {pokemon} Was Caught at {self.channel}  <https://twitch.tv/{self.channel[1:]}>", extra={"emoji": ":basketball:", "event": Events.CHAT_MENTION})
            else:               #Caught by someone else
                caughtby = msg.split(":",1)[1]
                #self.connection.privmsg(self.channel,f"Well Done {caughtby} enjoy your {pokemon} cezzbbPotato")
                logger.info(f"{pokemon} at {self.channel} Excaped but was caught by {caughtby}  <https://twitch.tv/{self.channel[1:]}>", extra={"emoji": ":basketball:", "event": Events.CHAT_MENTION})

        pokenoball = f"@{self._nickname.lower()} You don't own that ball. Check the extension to see your items" #Pokemon No Ball then throw
        if pokenoball in msg:
            pokemon = msg.split(" ")[0]        
            # nickname!username@nickname.tmi.twitch.tv
            nick = event.source.split("!", 1)[0]
            time.sleep(random.randrange(2,10))
            self.connection.privmsg(self.channel,f"!pokemart greatball 3")
            time.sleep(random.randrange(1,5))
            self.connection.privmsg(self.channel,f"!pokecatch greatball")
            logger.info(f"New Ball Purchased at <https://twitch.tv/{self.channel[1:]}>", extra={"emoji": ":basketball:", "event": Events.CHAT_MENTION})
            
    def on_ctcp(self, connection, event):
        msg = event.arguments[1]
        nick = event.source.split("!", 1)[0]
        # also self._realname
        # if msg.startswith(f"@{self._nickname}"):
       
        pokenew = 'Catch it using !pokecatch' # Define message for a new pokemon
        if pokenew in msg:
            pokemon = msg.split(" ")[3]                
            # nickname!username@nickname.tmi.twitch.tv
            nick = event.source.split("!", 1)[0]
            time.sleep(random.randrange(1,10))
            self.connection.privmsg(self.channel,"!pokecatch greatball")
            logger.info(f"Pokemon {pokemon} Spawned in at {self.channel} <https://twitch.tv/{self.channel[1:]}>)", extra={"emoji": ":basketball:", "event": Events.CHAT_MENTION})
        
        """ END OF POKEMON CODE """


class ThreadChat(Thread):
    def __deepcopy__(self, memo):
        return None

    def __init__(self, username, token, channel):
        super(ThreadChat, self).__init__()

        self.username = username
        self.token = token
        self.channel = channel
        self.chat_irc = None

    def run(self):
        self.chat_irc = ClientIRC(self.username, self.token, self.channel)
        logger.info(
            f"Join IRC Chat: {self.channel}", extra={"emoji": ":speech_balloon:"}
        )
        self.chat_irc.start()


    def stop(self):
        if self.chat_irc is not None:
            logger.info(
                f"Leave IRC Chat: {self.channel}", extra={"emoji": ":speech_balloon:"}
            )
            self.chat_irc.die()
