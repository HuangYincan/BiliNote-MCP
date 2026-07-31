# exceptions.py
from app.enmus.exception import ProviderErrorEnum


class NoteError(Exception):
    def __init__(self, message: str,code: ProviderErrorEnum) -> None:
        super().__init__(message)
        self.code=code
        self.message = message