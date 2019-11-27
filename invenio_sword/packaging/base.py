import typing

from invenio_sword.api import SWORDDeposit


class Packaging:
    def ingest(
        self,
        *,
        record: SWORDDeposit,
        stream: typing.BinaryIO,
        filename: str = None,
        content_type: str
    ):
        raise NotImplementedError
