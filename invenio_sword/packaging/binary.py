import typing
import mimetypes

from invenio_files_rest.models import ObjectVersion
from invenio_sword.api import SWORDDeposit
from .base import Packaging


__all__ = ['BinaryPackaging']


class BinaryPackaging(Packaging):
    def ingest(self, *, record: SWORDDeposit, stream: typing.BinaryIO, filename: str=None, content_type: str):
        if not filename:
            filename = "data" + mimetypes.guess_extension(content_type)

        ObjectVersion.create(record.bucket, filename, stream=stream)
