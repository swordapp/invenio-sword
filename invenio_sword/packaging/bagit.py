from __future__ import annotations

import mimetypes
import os
import shutil
import tempfile
import uuid
import zipfile
from typing import Collection

import bagit
from invenio_files_rest.models import ObjectVersion
from sword3common.constants import PackagingFormat
from sword3common.exceptions import ContentMalformed
from sword3common.exceptions import ContentTypeNotAcceptable
from sword3common.exceptions import ValidationFailed

from ..enum import ObjectTagKey
from ..metadata import SWORDMetadata
from ..utils import TagManager
from .base import Packaging

__all__ = ["SWORDBagItPackaging"]


class SWORDBagItPackaging(Packaging):
    content_type = "application/zip"
    packaging_name = PackagingFormat.SwordBagIt

    def get_original_deposit_filename(
        self, filename: str = None, media_type: str = None
    ) -> str:
        return self.record.original_deposit_key_prefix + "bagit-{}.zip".format(
            uuid.uuid4()
        )

    def unpack(self, object_version: ObjectVersion):
        if object_version.mimetype != self.content_type:
            raise ContentTypeNotAcceptable(
                "Content-Type must be {}".format(self.content_type)
            )

        with tempfile.TemporaryDirectory() as path:
            try:
                with tempfile.TemporaryFile() as f:
                    with object_version.file.storage().open() as stream:
                        shutil.copyfileobj(stream, f)
                    f.seek(0)
                    zip = zipfile.ZipFile(f)
                    zip.extractall(path)
                    zip.close()
                    f.seek(0)

                bag = bagit.Bag(path)
                bag.validate()

                if next(bag.files_to_be_fetched(), None):
                    raise ValidationFailed("fetch.txt not supported in SWORD BagIt")

                self.record["bagitInfo"] = bag.info

                # Ingest any SWORD metadata
                metadata_path = os.path.join(path, "metadata/sword.json")
                if (
                    os.path.exists(metadata_path)
                    and "metadata/sword.json" in bag.entries
                ):
                    with open(metadata_path, "rb") as metadata_f:
                        self.record.set_metadata(
                            metadata_f,
                            metadata_class=SWORDMetadata,
                            content_type="application/ld+json",
                            derived_from=object_version.key,
                            replace=True,
                        )
                        self.record.commit()

                # Ingest payload files
                for name in bag.payload_entries():
                    with open(os.path.join(path, name), "rb") as payload_f:

                        self._set_file_content(
                            key=name.split(os.path.sep, 1)[-1],
                            media_type=mimetypes.guess_type(name)[0],
                            stream=payload_f,
                        )

                return set(bag.payload_entries())
            except bagit.BagValidationError as e:
                raise ValidationFailed(e.message) from e
            except bagit.BagError as e:
                raise ContentMalformed(*e.args) from e
            except zipfile.BadZipFile as e:
                raise ContentMalformed("Bad ZIP file") from e

    def get_file_list(self, object_version: ObjectVersion) -> Collection[str]:
        with object_version.file.storage().open() as f, zipfile.ZipFile(f) as zip:
            return [
                zipinfo.filename[5:]
                for zipinfo in zip.filelist
                if zipinfo.filename.startswith("data/")
                and not zipinfo.filename.endswith("/")
            ]
