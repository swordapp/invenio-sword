from __future__ import annotations

from typing import Iterable
from typing import Optional

from invenio_files_rest.models import ObjectVersion

from invenio_sword.api import SWORDDeposit
from invenio_sword.typing import BytesReader


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
        original_deposit: Optional[ObjectVersion],
        unpackaged_objects: Iterable[ObjectVersion] = None,
    ):
        self.original_deposit = original_deposit
        self.ingested_objects = list(unpackaged_objects or ())
        if (
            self.original_deposit is not None
            and self.original_deposit not in self.ingested_objects
        ):
            self.ingested_objects.append(self.original_deposit)
