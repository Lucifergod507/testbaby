from user import User

class Database:
    def __init__(self) -> None:
        self._db = {}

    async def get(self, id: int) -> User:
        return self._db.setdefault(id, User(id))
    
db = Database()
