import mimetypes
import shutil
import tempfile
import uuid
import zipfile

from invenio_files_rest.models import ObjectVersion
from invenio_files_rest.models import ObjectVersionTag
from werkzeug.exceptions import UnsupportedMediaType

from ..api import SWORDDeposit
from .base import Packaging
from invenio_sword.enum import ObjectTagKey
from invenio_sword.typing import BytesReader

__all__ = ["SimpleZipPackaging"]


class SimpleZipPackaging(Packaging):
    content_type = "application/zip"
    packaging_name = "http://purl.org/net/sword/3.0/package/SimpleZip"

    def ingest(
        self,
        *,
        record: SWORDDeposit,
        stream: BytesReader,
        filename: str = None,
        content_type: str
    ):
        if content_type != self.content_type:
            raise UnsupportedMediaType

        original_deposit_filename = "original-deposit-{}.zip".format(uuid.uuid4())

        with tempfile.TemporaryFile() as f:
            shutil.copyfileobj(stream, f)
            f.seek(0)

            with zipfile.ZipFile(f) as zip:
                names = set(zip.namelist())

                for name in names:
                    object_version = ObjectVersion.create(
                        record.bucket,
                        name,
                        mimetype=mimetypes.guess_type(name)[0],
                        stream=zip.open(name),
                    )
                    ObjectVersionTag.create(
                        object_version=object_version,
                        key=ObjectTagKey.FileSetFile.value,
                        value="true",
                    )
                    ObjectVersionTag.create(
                        object_version=object_version,
                        key=ObjectTagKey.DerivedFrom.value,
                        value=original_deposit_filename,
                    )

            f.seek(0)

            original_deposit = ObjectVersion.create(
                record.bucket,
                original_deposit_filename,
                mimetype=self.content_type,
                stream=f,
            )
            ObjectVersionTag.create(
                object_version=original_deposit,
                key=ObjectTagKey.OriginalDeposit.value,
                value="true",
            )
            ObjectVersionTag.create(
                object_version=original_deposit,
                key=ObjectTagKey.Packaging.value,
                value=self.packaging_name,
            )

        return names | {original_deposit_filename}
