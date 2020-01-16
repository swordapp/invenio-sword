from __future__ import annotations

import functools
import logging
from typing import Optional
from typing import TYPE_CHECKING

from flask import current_app
from flask import url_for
from invenio_deposit.api import Deposit
from invenio_pidstore.resolver import Resolver
from invenio_records_files.api import FileObject

from invenio_sword.enum import ObjectTagKey

if TYPE_CHECKING:
    from .metadata import Metadata  # pragma: nocover


logger = logging.getLogger(__name__)


class SWORDFileObject(FileObject):
    def __init__(self, *args, pid, **kwargs):
        self.pid = pid
        return super().__init__(*args, **kwargs)

    @property
    def rest_file_url(self):
        return url_for(
            "invenio_sword.{}_file".format(self.pid.pid_type),
            pid_value=self.pid.pid_value,
            key=self.key,
            _external=True,
        )


class SWORDDeposit(Deposit):
    @property
    def file_cls(self):
        return functools.partial(SWORDFileObject, pid=self.pid)

    def get_status_as_jsonld(self):
        return {
            "@type": "Status",
            "metadata": {"@id": self.sword_metadata_url,},
            "fileSet": {"@id": self.sword_fileset_url,},
            "service": url_for(
                "invenio_sword.{}_service_document".format(self.pid.pid_type)
            ),
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
            "links": self.links,
        }

    @property
    def links(self):

        links = []
        for file in self.files:
            link = {
                "@id": file.rest_file_url,
                "contentType": file.obj.mimetype,
                "status": "http://purl.org/net/sword/3.0/filestate/ingested",
            }

            tags = {tag.key: tag.value for tag in file.tags}
            rels = set()
            if tags.get(ObjectTagKey.OriginalDeposit.value) == "true":
                rels.add("http://purl.org/net/sword/3.0/terms/originalDeposit")
            if tags.get(ObjectTagKey.FileSetFile.value) == "true":
                rels.add("http://purl.org/net/sword/3.0/terms/fileSetFile")
            derived_from = tags.get(ObjectTagKey.DerivedFrom.value)
            if derived_from:
                rels.add("http://purl.org/net/sword/3.0/terms/derivedResource")
                link["derivedFrom"] = url_for(
                    "invenio_sword.{}_file".format(self.pid.pid_type),
                    pid_value=self.pid.pid_value,
                    key=derived_from,
                    _external=True,
                )
            if ObjectTagKey.Packaging.value in tags:
                link["packaging"] = tags[ObjectTagKey.Packaging.value]

            link["rels"] = sorted(rels)

            links.append(link)

        return links

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
        elif self["_deposit"].get("status") == "published":
            states.append(
                {
                    "@id": "http://purl.org/net/sword/3.0/state/accepted",
                    "description": "the item is currently accepted",
                }
            )
        return states

    @property
    def sword_status_url(self):
        return url_for(
            "invenio_sword.{}_item".format(self.pid.pid_type),
            pid_value=self.pid.pid_value,
            _external=True,
        )

    @property
    def sword_metadata_url(self):
        return url_for(
            "invenio_sword.{}_metadata".format(self.pid.pid_type),
            pid_value=self.pid.pid_value,
            _external=True,
        )

    @property
    def sword_fileset_url(self):
        return url_for(
            "invenio_sword.{}_fileset".format(self.pid.pid_type),
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
                metadata_cls = current_app.config["SWORD_ENDPOINTS"][self.pid.pid_type][
                    "metadata_formats"
                ][self.sword_metadata_format]
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
            for metadata_format, metadata_cls in current_app.config["SWORD_ENDPOINTS"][
                self.pid.pid_type
            ]["metadata_formats"].items():
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
