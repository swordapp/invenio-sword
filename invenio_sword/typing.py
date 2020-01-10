try:
    from typing import Protocol
    from typing import runtime_checkable
except ImportError:  # pragma: nocover
    from typing_extensions import Protocol  # type: ignore
    from typing_extensions import runtime_checkable


@runtime_checkable
class BytesReader(Protocol):
    def read(self, amount: int = -1) -> bytes:
        ...  # pragma: nocover
