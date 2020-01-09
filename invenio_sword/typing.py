from typing import Protocol
from typing import runtime_checkable


@runtime_checkable
class BytesReader(Protocol):
    def read(self, amount: int = -1) -> bytes:
        ...
