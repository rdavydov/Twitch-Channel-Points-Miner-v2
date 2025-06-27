import abc
from threading import Timer
from typing import Callable

from TwitchChannelPointsMiner.classes.entities.Bet import Bet
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer
from TwitchChannelPointsMiner.classes.event_prediction.Bettor import (
    TimerEventPredictionBettor,
)
from TwitchChannelPointsMiner.classes.event_prediction.Manager import (
    EventPredictionManager,
    EventPredictionManagerBase,
    EventPredictionTracker,
)


class EventPredictionManagerFactoryBase(object, metaclass=abc.ABCMeta):
    """Base factory class for producing EventPredictionManagerBase objects."""

    @abc.abstractmethod
    def produce(
        self, place_bet: Callable[[Streamer, str, Bet], None]
    ) -> EventPredictionManagerBase:
        """
        Produces a new EventPredictionManager for the given place_bet function.

        :param place_bet: A function that can place bets,
        :return: The created manager.
        """
        pass


class EventPredictionManagerFactory(EventPredictionManagerFactoryBase):
    """
    EventPredictionManagerFactoryBase class for producing EventPredictionManagers that implement the default
    EventPrediction functionality. Events should all get tracked and betting on events should take place according to
    the Streamer's BetSettings.
    """

    def produce(
        self, place_bet: Callable[[Streamer, str, Bet], None]
    ) -> EventPredictionManager:
        return EventPredictionManager(
            EventPredictionTracker(), TimerEventPredictionBettor(place_bet, Timer)
        )
