"""Infrastructure failure which may be safely exposed by an HTTP adapter."""


class PersistenceError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Persistence is temporarily unavailable")
