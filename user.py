
class User:
    def __init__(self, id: int) -> None:
        self.id: int = id
        self.working: bool = False
        self.stop_work: bool = False
        self.links: list = []
        self.waiting_for_config: bool = False
        self.last_edited_at: float = 0
