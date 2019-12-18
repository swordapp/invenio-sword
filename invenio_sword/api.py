from __future__ import annotations

import functools
import logging
from typing import Optional
from typing import TYPE_CHECKING

from flask import current_app
from flask import url_for
from invenio_deposit.api import Deposit
from invenio_files_rest.models import FileInstance
from invenio_pidstore.resolver import Resolver
from invenio_records_files.api import FileObject

if TYPE_CHECKING:
    from .metadata import Metadata  # pragma: nocover


logger = logging.getLogger(__name__)


class SWORDFileObject(FileObject):
    obj: FileInstance

    def __init__(self, *args, record_pid_value: str, **kwargs):
        self.record_pid_value = record_pid_value
        return super().__init__(*args, **kwargs)

    @property
    def sword_file_url(self):
        return url_for(
            "invenio_sword.deposit-file",
            pid_value=self.record_pid_value,
            file_id=self.obj.file_id,
            _external=True,
        )


class SWORDDeposit(Deposit):
    @property
    def file_cls(self):
        return functools.partial(SWORDFileObject, record_pid_value=self.pid.pid_value)

    def get_status_as_jsonld(self):
        return {
            "@type": "Status",
            "metadata": {"@id": self.sword_metadata_url,},
            "fileSet": {"@id": self.sword_fileset_url,},
            "service": url_for("invenio_sword.service-document"),
            "state": self.sword_states,
            "actions": {
                "getMetadata": True,
                "getFiles": True,
                "appendMetadata": True,
                "appendFiles": True,
                "replaceMetadata": True,
                "replaceFiles": True,
                "deleteMetadata": True,
                "deleteFiles": True,
                "deleteObject": True,
            },
            "links": [
                {
                    "@id": file.sword_file_url,
                    "rel": ["http://purl.org/net/sword/3.0/terms/fileSetFile"],
                    "contentType": file.obj.mimetype,
                    "status": "http://purl.org/net/sword/3.0/filestate/ingested",
                }
                for file in self.files
            ],
        }

    @property
    def sword_states(self):
        states = []
        if self["_deposit"].get("status") == "draft":
            states.append(
                {
                    "@id": "http://purl.org/net/sword/3.0/state/inProgress",
                    "description": "the item is currently inProgress",
                }
            )
        return states

    @property
    def sword_status_url(self):
        return url_for(
            "invenio_sword.deposit-status", pid_value=self.pid.pid_value, _external=True
        )

    @property
    def sword_metadata_url(self):
        return url_for(
            "invenio_sword.deposit-metadata",
            pid_value=self.pid.pid_value,
            _external=True,
        )

    @property
    def sword_fileset_url(self):
        return url_for(
            "invenio_sword.deposit-fileset",
            pid_value=self.pid.pid_value,
            _external=True,
        )

    @property
    def sword_metadata_format(self):
        return self.get("swordMetadataFormat")

    @property
    def sword_metadata(self) -> Optional[Metadata]:
        if self.sword_metadata_format:
            try:
                metadata_cls = current_app.config["SWORD_METADATA_FORMATS"][
                    self.sword_metadata_format
                ]
            except KeyError:
                logger.warning(
                    "Metadata format for record %s (%s) not supported",
                    self.pid.pid_value,
                    self.sword_metadata_format,
                )
                return None
            return metadata_cls(self["swordMetadata"])
        else:
            return None

    @sword_metadata.setter
    def sword_metadata(self, metadata: Optional[Metadata]):
        if metadata is None:
            del self["swordMetadataFormat"]
            del self["swordMetadata"]
        else:
            for metadata_format, metadata_cls in current_app.config[
                "SWORD_METADATA_FORMATS"
            ].items():
                if isinstance(metadata, metadata_cls):
                    break
            else:
                raise ValueError(
                    "Metadata format %s is not configured", type(metadata).__qualname__
                )
            self["swordMetadataFormat"] = metadata_format
            self["swordMetadata"] = metadata.to_json()
            metadata.update_record_metadata(self)


pid_resolver = Resolver(
    pid_type="depid",
    object_type="rec",
    getter=functools.partial(SWORDDeposit.get_record, with_deleted=True),
)
