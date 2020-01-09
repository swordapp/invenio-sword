from __future__ import annotations

import typing

from invenio_sword.api import SWORDDeposit
from invenio_sword.typing import BytesReader


class Metadata:
    content_type: str

    @classmethod
    def from_document(
        cls, document: BytesReader, content_type: str, encoding: str = "utf_8"
    ) -> Metadata:
        raise NotImplementedError

    def update_record_metadata(self, record: SWORDDeposit):
        raise NotImplementedError

    def to_json(self) -> typing.Dict[str, typing.Any]:
        raise NotImplementedError

    def to_document(self, metadata_url):
        raise NotImplementedError


class JSONMetadata(Metadata):
    @classmethod
    def from_document(
        cls,
        document: typing.Union[BytesReader, dict],
        content_type: str,
        encoding: str = "utf_8",
    ) -> Metadata:
        raise NotImplementedError
