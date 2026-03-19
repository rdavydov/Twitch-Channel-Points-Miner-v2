import abc

from TwitchChannelPointsMiner.classes.gql import Error


class GQLError(abc.ABC, Exception):
    """Abstract base class for GQL errors."""

    def recoverable(self) -> bool:
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
        # If all the individual Errors are recoverable then this is too
        return all(error.recoverable for error in self.errors)

    def __str__(self):
        return f"GQL Operation '{self.operation_name}' returned errors: {self.errors}"

    def __repr__(self):
        return str(self)


class InvalidJsonShapeException(GQLError):
    """Raised when a GQL response has an unexpected shape."""

    def __init__(self, path: list[str | int], message: str):
        self.path = path
        """The path in the JSON to the unexpected value."""
        self.message = message
        """Information about the unexpected value."""

    def recoverable(self):
        # This is likely an API change and so can't be recovered
        return False

    def __str__(self):
        def render_path_item(item: int | str) -> str:
            if isinstance(item, int):
                return str(item)
            else:
                return f'"{item}"'

        return f'JSON at [{", ".join(map(render_path_item, reversed(self.path)))}] has an invalid shape: {self.message}'

    def __repr__(self):
        return str(self)


class RetryError(GQLError):
    """Raised when multiple attempts to perform a GQL operation fail."""

    def __init__(self, operation_name: str, errors: list):
        self.operation_name = operation_name
        """The name of the SQL operation."""
        self.errors = errors
        """The list of errors that occurred."""

    def __str__(self):
        return f"GQL Operation '{self.operation_name}' failed all {len(self.errors)} attempts, errors:\n{self.errors}"

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        if isinstance(other, RetryError):
            return (
                self.operation_name == other.operation_name
                and len(self.errors) == len(other.errors)
                and all(
                    self.errors[index] == other.errors[index]
                    for index in range(len(self.errors))
                )
            )
        else:
            return False
