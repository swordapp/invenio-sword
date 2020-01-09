from invenio_sword.api import SWORDDeposit
from invenio_sword.typing import BytesReader


class Packaging:
    def ingest(
        self,
        *,
        record: SWORDDeposit,
        stream: BytesReader,
        filename: str = None,
        content_type: str
    ):
        raise NotImplementedError  # pragma: nocover
