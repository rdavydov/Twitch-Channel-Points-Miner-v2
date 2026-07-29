import abc

from TwitchChannelPointsMiner.classes.Settings import Events


class EventHook(abc.ABC):
    """
    Abstract base class for an object that can send event messages. e.g.:

        .. code-block:: python

        class ExampleEventHook(EventHook):
            def __init__(self, webhook_api: str):
                self.webhook_api = webhook_api

            def send(self, message: str, event: Events) -> None:
                requests.post(self.webhook_api, data={content=message})

            def validate_record(self, record) -> bool:
                return True

    In this example `ExampleEventHook` sends the message to some remote webhook that exists at `webhook_api`, all
    messages get sent because all log records return `True` from `validate_record`.
    """

    @abc.abstractmethod
    def send(self, message: str, event: Events) -> None:
        """
        Sends a message for a give type of Event.
        :param message: The message to send.
        :param event: The event type of the message.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def validate_record(self, record) -> bool:
        """
        Validates a log record. Returns True if the record is valid and False otherwise.
        :param record: Log record to validate.
        :return: True if the record is valid and False otherwise.
        """
        raise NotImplementedError()

    def validate_and_send(self, record) -> None:
        """
        Validates a log record and sends it if it's valid.
        :param record: Log record to validate and send.
        """
        if self.validate_record(record):
            self.send(record.msg, record.event)


class LogAttributeValidatingEventHook(EventHook, abc.ABC):
    """
    Abstract EventHook that validates log records based on whether a particular attribute is set. e.g.:

        .. code-block:: python

        class ExampleHook(LogAttributeValidatingEventHook):
            def __init__(self):
                super().__init__("skip_example_hook")

            def send(self, message: str, event: Events) -> None:
                ...

        record = {
            'msg': 'Hello World!',
            'skip_example_hook': True
        }
        hook = ExampleHook()
        hook.validate_record(record)# Returns False

    In this example `ExampleHook` passes "skip_example_hook" to `super().__init__`, later when `validate_record` is
    called the record passed contains an attribute with that name and so returns `False`.
    """

    def __init__(self, skip_attr_name: str):
        """
        :param skip_attr_name: The name of the attribute to check for on log records.
        """
        self.skip_attr_name = skip_attr_name

    def validate_record(self, record):
        """
        Returns `False` if the record contains an attribute with the same name as the value of `self.skip_attr_name`.
        :param record: The log record to validate.
        :return: True if the record is valid.
        """
        return False if hasattr(record, self.skip_attr_name) is True else True
