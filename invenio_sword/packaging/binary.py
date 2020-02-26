from __future__ import annotations

import mimetypes
import typing

from invenio_files_rest.models import ObjectVersion
from sword3common.constants import PackagingFormat

from ..enum import ObjectTagKey
from ..typing import BytesReader
from ..utils import TagManager
from .base import IngestResult
from .base import Packaging

if typing.TYPE_CHECKING:  # pragma: nocover
    from ..api import SWORDDeposit

__all__ = ["BinaryPackaging"]


class BinaryPackaging(Packaging):
    packaging_name = PackagingFormat.Binary

    def ingest(
        self,
        *,
        record: SWORDDeposit,
        stream: BytesReader,
        filename: str = None,
        content_type: str
    ):
        if not filename:
            extension = mimetypes.guess_extension(content_type)
            if extension:
                filename = "data" + extension
            else:
                filename = "data"

        object_version = ObjectVersion.create(
            record.bucket, filename, mimetype=content_type, stream=stream
        )

        tags = TagManager(object_version)
        tags.update(
            {ObjectTagKey.OriginalDeposit: "true", ObjectTagKey.FileSetFile: "true",}
        )

        return IngestResult(object_version)
