import abc

from TwitchChannelPointsMiner.classes.entities.PubsubTopic import PubsubTopic


class WebSocketPool(abc.ABC):
    """Abstract base class for a WebSocket pool that allows submitting PubsubTopics."""

    @abc.abstractmethod
    def start(self):
        """Starts the WebSocket Pool."""
        raise NotImplementedError()

    @abc.abstractmethod
    def end(self):
        """Ends the WebSocket Pool."""
        raise NotImplementedError()

    @abc.abstractmethod
    def submit(self, topic: PubsubTopic):
        """
        Submits the given topic to an available client.
        :param topic: The topic to submit.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def check_stale_connections(self):
        """Finds any stale clients, i.e. no recent ping, and reconnects them."""
        raise NotImplementedError()
