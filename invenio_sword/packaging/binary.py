import mimetypes

from invenio_files_rest.models import ObjectVersion

from ..api import SWORDDeposit
from .base import Packaging
from invenio_sword.typing import BytesReader

__all__ = ["BinaryPackaging"]


class BinaryPackaging(Packaging):
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

        ObjectVersion.create(
            record.bucket, filename, mimetype=content_type, stream=stream
        )

        return {filename}
