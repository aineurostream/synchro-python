class GraphEdge:
    def __init__(
        self,
        source: str,
        target: str,
    ) -> None:
        self.source = source
        self.target = target

    @property
    def id(self) -> str:
        return f"[{self.source} -> {self.target}]"

    def __repr__(self) -> str:
        return self.id
