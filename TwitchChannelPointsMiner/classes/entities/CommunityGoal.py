class CommunityGoal(object):
    __slots__ = [
        "goal_id",
        "title",
        "is_in_stock",
        "points_contributed",
        "amount_needed",
        "per_stream_user_maximum_contribution",
        "status"
    ]

    def __init__(
            self,
            goal_id,
            title,
            is_in_stock,
            points_contributed,
            amount_needed,
            per_stream_user_maximum_contribution,
            status
    ):
        self.goal_id = goal_id
        self.title = title
        self.is_in_stock = is_in_stock
        self.points_contributed = points_contributed
        self.amount_needed = amount_needed
        self.per_stream_user_maximum_contribution = per_stream_user_maximum_contribution
        self.status = status

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.goal_id == other.goal_id
        else:
            return False

    def __repr__(self) -> str:
        return f"CommunityGoal(goal_id: {self.goal_id}, title: {self.title}, is_in_stock: {self.is_in_stock}, points_contributed: {self.points_contributed}, amount_needed: {self.amount_needed}, per_stream_user_maximum_contribution: {self.per_stream_user_maximum_contribution}, status: {self.status})"

    def amount_left(self):
        return self.amount_needed - self.points_contributed

    @classmethod
    def from_gql(cls, gql_goal):
        return cls(
            gql_goal["id"],
            gql_goal["title"],
            gql_goal["isInStock"],
            gql_goal["pointsContributed"],
            gql_goal["amountNeeded"],
            gql_goal["perStreamUserMaximumContribution"],
            gql_goal["status"]
        )

    @classmethod
    def from_pubsub(cls, pubsub_goal):
        return cls(
            pubsub_goal["id"],
            pubsub_goal["title"],
            pubsub_goal["is_in_stock"],
            pubsub_goal["points_contributed"],
            pubsub_goal["goal_amount"],
            pubsub_goal["per_stream_maximum_user_contribution"],
            pubsub_goal["status"]
        )
