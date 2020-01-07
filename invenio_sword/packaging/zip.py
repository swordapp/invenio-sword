import mimetypes
import shutil
import tempfile
import typing
import zipfile

from invenio_files_rest.models import ObjectVersion
from werkzeug.exceptions import UnsupportedMediaType

from ..api import SWORDDeposit
from .base import Packaging

__all__ = ["SimpleZipPackaging"]


class SimpleZipPackaging(Packaging):
    content_type = "application/zip"

    def ingest(
        self,
        *,
        record: SWORDDeposit,
        stream: typing.BinaryIO,
        filename: str = None,
        content_type: str
    ):
        if content_type != self.content_type:
            raise UnsupportedMediaType

        with tempfile.TemporaryFile() as f:
            shutil.copyfileobj(stream, f)
            f.seek(0)

            zip = zipfile.ZipFile(f)

            for name in zip.namelist():
                ObjectVersion.create(
                    record.bucket,
                    name,
                    mimetype=mimetypes.guess_type(name)[0],
                    stream=zip.open(name),
                )
