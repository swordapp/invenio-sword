from __future__ import annotations

import mimetypes
import shutil
import tempfile
import uuid
import zipfile
from typing import Collection

from invenio_files_rest.models import ObjectVersion
from sword3common.constants import PackagingFormat
from sword3common.exceptions import ContentMalformed
from sword3common.exceptions import ContentTypeNotAcceptable

from ..enum import ObjectTagKey
from ..utils import TagManager
from .base import Packaging


__all__ = ["SimpleZipPackaging"]


class SimpleZipPackaging(Packaging):
    content_type = "application/zip"
    packaging_name = PackagingFormat.SimpleZip

    def get_original_deposit_filename(
        self, filename: str = None, media_type: str = None
    ) -> str:
        return self.record.original_deposit_key_prefix + "simple-zip-{}.zip".format(
            uuid.uuid4()
        )

    def unpack(self, object_version: ObjectVersion):
        if object_version.mimetype != self.content_type:
            raise ContentTypeNotAcceptable(
                "Content-Type must be {}".format(self.content_type)
            )

        try:
            with tempfile.TemporaryFile() as f:
                with object_version.file.storage().open() as stream:
                    shutil.copyfileobj(stream, f)
                f.seek(0)

                with zipfile.ZipFile(f) as zip:
                    names = set(zip.namelist())

                    for name in names:
                        self._set_file_content(
                            key=name,
                            media_type=mimetypes.guess_type(name)[0],
                            stream=zip.open(name),
                        )
                return names
        except zipfile.BadZipFile as e:
            raise ContentMalformed("Bad ZIP file") from e

    def get_file_list(self, object_version: ObjectVersion) -> Collection[str]:
        with object_version.file.storage().open() as f, zipfile.ZipFile(f) as zip:
            return [
                zipinfo.filename
                for zipinfo in zip.filelist
                if not zipinfo.filename.endswith("/")
            ]
