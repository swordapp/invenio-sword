import typing

from invenio_sword.api import SWORDDeposit


class Metadata:
    @classmethod
    def from_document(cls, document: typing.BinaryIO, content_type: str) -> "Metadata":
        raise NotImplementedError

    def update_record_metadata(self, record: SWORDDeposit):
        raise NotImplementedError
