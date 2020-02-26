from __future__ import annotations

import mimetypes
import shutil
import tempfile
import typing
import uuid
import zipfile

from invenio_files_rest.models import ObjectVersion
from sword3common.constants import PackagingFormat
from sword3common.exceptions import ContentMalformed
from sword3common.exceptions import ContentTypeNotAcceptable

from ..enum import ObjectTagKey
from ..typing import BytesReader
from ..utils import TagManager
from .base import IngestResult
from .base import Packaging

if typing.TYPE_CHECKING:  # pragma: nocover
    from ..api import SWORDDeposit

__all__ = ["SimpleZipPackaging"]


class SimpleZipPackaging(Packaging):
    content_type = "application/zip"
    packaging_name = PackagingFormat.SimpleZip

    def ingest(
        self,
        *,
        record: SWORDDeposit,
        stream: BytesReader,
        filename: str = None,
        content_type: str
    ):
        if content_type != self.content_type:
            raise ContentTypeNotAcceptable(
                "Content-Type must be {}".format(content_type)
            )

        original_deposit_filename = (
            record.original_deposit_key_prefix
            + "simple-zip-{}.zip".format(uuid.uuid4())
        )
        unpackaged_objects = []

        try:
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

                        tags = TagManager(object_version)
                        tags.update(
                            {
                                ObjectTagKey.FileSetFile: "true",
                                ObjectTagKey.DerivedFrom: original_deposit_filename,
                            }
                        )
                        unpackaged_objects.append(object_version)

                f.seek(0)

                original_deposit = ObjectVersion.create(
                    record.bucket,
                    original_deposit_filename,
                    mimetype=self.content_type,
                    stream=f,
                )

                tags = TagManager(original_deposit)
                tags.update(
                    {
                        ObjectTagKey.OriginalDeposit: "true",
                        ObjectTagKey.Packaging: self.packaging_name,
                    }
                )

            return IngestResult(original_deposit, unpackaged_objects)
        except zipfile.BadZipFile as e:
            raise ContentMalformed("Bad ZIP file") from e
