import mimetypes

from invenio_files_rest.models import ObjectVersion
from invenio_files_rest.models import ObjectVersionTag

from ..api import SWORDDeposit
from .base import Packaging
from invenio_sword.enum import ObjectTagKey
from invenio_sword.typing import BytesReader

__all__ = ["BinaryPackaging"]


class BinaryPackaging(Packaging):
    packaging_name = "http://purl.org/net/sword/3.0/package/Binary"

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

        ObjectVersionTag.create(
            object_version=object_version,
            key=ObjectTagKey.OriginalDeposit.value,
            value="true",
        )
        ObjectVersionTag.create(
            object_version=object_version,
            key=ObjectTagKey.FileSetFile.value,
            value="true",
        )

        return {filename}
