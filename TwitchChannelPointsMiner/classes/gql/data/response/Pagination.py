from typing import Generic, TypeVar


class PageInfo:
    """Information about the current pagination state."""

    def __init__(self, has_next_page: bool, start_cursor: str | None = None, end_cursor: str | None = None):
        self.has_next_page = has_next_page
        """Whether there are more pages available."""
        self.start_cursor = start_cursor
        """The cursor at the start of the page."""
        self.end_cursor = end_cursor
        """The cursor at the end of the page."""

    def __repr__(self) -> str:
        return f"PageInfo({self.__dict__})"


T = TypeVar("T")


class Edge(Generic[T]):
    """Representation of a Pagination Edge."""

    def __init__(self, cursor: str, node: T):
        self.cursor = cursor
        """The cursor of this Edge. Can be used to resume Paginated requests from this point."""
        self.node = node
        """The entity at this point of Pagination."""

    def __repr__(self) -> str:
        return f"Edge({self.__dict__})"


class Paginated(Generic[T]):
    """Representation of a GQL Paginated response."""

    def __init__(self, edges: list[Edge[T]], page_info: PageInfo):
        self.edges = edges
        """The "edges" are a wrapper containing the actual value we want."""
        self.page_info = page_info
        """Information about the current pagination state."""

    def __repr__(self) -> str:
        return f"Paginated({self.__dict__})"
