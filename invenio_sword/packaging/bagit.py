import mimetypes
import os
import shutil
import tempfile
import uuid
import zipfile

import bagit
from invenio_files_rest.models import ObjectVersion
from invenio_files_rest.models import ObjectVersionTag
from werkzeug.exceptions import BadRequest
from werkzeug.exceptions import NotImplemented
from werkzeug.exceptions import UnsupportedMediaType

from .base import Packaging
from invenio_sword.api import SWORDDeposit
from invenio_sword.enum import ObjectTagKey
from invenio_sword.metadata import SWORDMetadata
from invenio_sword.typing import BytesReader

__all__ = ["SWORDBagItPackaging"]


class SWORDBagItPackaging(Packaging):
    content_type = "application/zip"
    packaging_name = "http://purl.org/net/sword/3.0/package/SWORDBagIt"

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

        with tempfile.TemporaryDirectory() as path:
            try:
                with tempfile.TemporaryFile() as f:
                    shutil.copyfileobj(stream, f)
                    f.seek(0)
                    zip = zipfile.ZipFile(f)
                    zip.extractall(path)
                    zip.close()
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

                bag = bagit.Bag(path)
                bag.validate()

                if next(bag.files_to_be_fetched(), None):
                    raise NotImplemented(  # noqa: F901
                        "fetch.txt not supported in SWORD BagIt"
                    )

                record["bagitInfo"] = bag.info

                # Ingest any SWORD metadata
                metadata_path = os.path.join(path, "metadata/sword.json")
                if (
                    os.path.exists(metadata_path)
                    and "metadata/sword.json" in bag.entries
                ):
                    with open(metadata_path, "rb") as metadata_f:
                        record.sword_metadata = SWORDMetadata.from_document(
                            metadata_f, content_type=SWORDMetadata.content_type,
                        )

                # Ingest payload files
                for name in bag.payload_entries():
                    with open(os.path.join(path, name), "rb") as payload_f:
                        object_version = ObjectVersion.create(
                            record.bucket,
                            name.split(os.path.sep, 1)[-1],
                            mimetype=mimetypes.guess_type(name)[0],
                            stream=payload_f,
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
                return {
                    name.split(os.path.sep, 1)[-1] for name in bag.payload_entries()
                } | {original_deposit_filename}
            except bagit.BagValidationError as e:
                raise BadRequest(e.message) from e
            except bagit.BagError as e:
                raise BadRequest(*e.args) from e
