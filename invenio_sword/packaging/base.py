from __future__ import annotations

import typing

from invenio_files_rest.models import ObjectVersion

from ..typing import BytesReader

if typing.TYPE_CHECKING:
    from ..api import SWORDDeposit


class Packaging:
    packaging_name: str

    def ingest(
        self,
        *,
        record: SWORDDeposit,
        stream: BytesReader,
        filename: str = None,
        content_type: str
    ) -> IngestResult:
        raise NotImplementedError  # pragma: nocover


class IngestResult:
    def __init__(
        self,
        original_deposit: typing.Optional[ObjectVersion],
        unpackaged_objects: typing.Iterable[ObjectVersion] = None,
    ):
        self.original_deposit = original_deposit
        self.ingested_objects = list(unpackaged_objects or ())
        if (
            self.original_deposit is not None
            and self.original_deposit not in self.ingested_objects
        ):
            self.ingested_objects.append(self.original_deposit)
