import abc

from TwitchChannelPointsMiner.classes.gql import Error


class GQLError(abc.ABC, Exception):
    """Abstract base class for GQL errors."""

    def recoverable(self):
        """True if this error can be recovered."""
        return False


class GQLResponseErrors(GQLError):
    """Raised when a GQL response contained Errors."""

    def __init__(self, operation_name: str, errors: list[Error]):
        self.operation_name = operation_name
        """The name of the SQL operation."""
        self.errors = errors
        """The list of errors in the response."""

    def recoverable(self):
        return all(error for error in self.errors if error.recoverable)

    def __str__(self):
        return f"GQL Operation '{self.operation_name}' returned errors: {self.errors}"


class InvalidJsonShapeException(Exception):
    """Raised when a GQL response has na unexpected shape."""

    def __init__(self, path: list[str | int], message: str):
        self.path = path
        """The path in the JSON to the unexpected value."""
        self.message = message
        """Information about the unexpected value."""

    def __str__(self):
        def render_path_item(item: int | str) -> str:
            if isinstance(item, int):
                return str(item)
            else:
                return f'"{item}"'

        return f'JSON at [{", ".join(map(render_path_item, reversed(self.path)))}] has an invalid shape: {self.message}'


class RetryError(Exception):
    """Raised when multiple attempts to perform a GQL operation fail."""

    def __init__(self, operation_name: str, errors: list):
        self.operation_name = operation_name
        """The name of the SQL operation."""
        self.errors = errors
        """The list of errors that occurred."""

    def __str__(self):
        return f"GQL Operation '{self.operation_name}' failed all {len(self.errors)} attempts, errors: {self.errors}"

    def __eq__(self, other):
        if isinstance(other, RetryError):
            return self.operation_name == other.operation_name and len(self.errors) == len(other.errors) and all(
                self.errors[index] == other.errors[index] for index in range(len(self.errors))
            )
        else:
            return False
