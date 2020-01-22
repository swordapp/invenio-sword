from __future__ import annotations

import functools
import io
import logging
import typing

from flask import url_for
from invenio_deposit.api import Deposit
from invenio_files_rest.models import ObjectVersion
from invenio_files_rest.models import ObjectVersionTag
from invenio_pidstore.resolver import Resolver
from invenio_records_files.api import FileObject
from sqlalchemy import true
from werkzeug.exceptions import BadRequest
from werkzeug.exceptions import Conflict
from werkzeug.http import parse_options_header

from .metadata import JSONMetadata
from .metadata import Metadata
from invenio_sword.enum import ObjectTagKey
from invenio_sword.metadata import SWORDMetadata
from invenio_sword.typing import BytesReader


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
            "@id": self.sword_status_url,
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
            rel = set()
            if tags.get(ObjectTagKey.OriginalDeposit.value) == "true":
                rel.add("http://purl.org/net/sword/3.0/terms/originalDeposit")
            if tags.get(ObjectTagKey.FileSetFile.value) == "true":
                rel.add("http://purl.org/net/sword/3.0/terms/fileSetFile")
            derived_from = tags.get(ObjectTagKey.DerivedFrom.value)
            if derived_from:
                rel.add("http://purl.org/net/sword/3.0/terms/derivedResource")
                link["derivedFrom"] = url_for(
                    "invenio_sword.{}_file".format(self.pid.pid_type),
                    pid_value=self.pid.pid_value,
                    key=derived_from,
                    _external=True,
                )
            if ObjectTagKey.Packaging.value in tags:
                link["packaging"] = tags[ObjectTagKey.Packaging.value]
            if ObjectTagKey.MetadataFormat.value in tags:
                rel.add("http://purl.org/net/sword/3.0/terms/formattedMetadata")
                link["metadataFormat"] = tags[ObjectTagKey.MetadataFormat.value]

            link["rel"] = sorted(rel)

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
    def metadata_key_prefix(self):
        return ".metadata-{}/".format(self.pid.pid_value)

    @property
    def original_deposit_key_prefix(self):
        return ".original-deposit-{}/".format(self.pid.pid_value)

    @property
    def sword_metadata(self):
        raise NotImplementedError

    def set_metadata(
        self,
        source: typing.Optional[typing.Union[BytesReader, dict]],
        metadata_class: typing.Type[Metadata],
        content_type: str = None,
        replace: bool = True,
    ) -> typing.Optional[Metadata]:
        if isinstance(source, dict) and not issubclass(metadata_class, JSONMetadata):
            raise BadRequest(
                "Metadata-Format must be JSON-based to use Metadata+By-Reference deposit"
            )

        if not content_type:
            content_type = metadata_class.content_type

        existing_metadata_object = (
            ObjectVersion.query.join(ObjectVersion.tags)
            .filter(
                ObjectVersion.is_head == true(),
                ObjectVersion.file_id.isnot(None),
                ObjectVersion.bucket == self.bucket,
                ObjectVersionTag.key == ObjectTagKey.MetadataFormat.value,
                ObjectVersionTag.value == metadata_class.metadata_format,
            )
            .first()
        )

        if source is None:

            if replace and existing_metadata_object:
                ObjectVersion.delete(
                    bucket=existing_metadata_object.bucket,
                    key=existing_metadata_object.key,
                )

            if replace and (
                self.get("swordMetadataSourceFormat") == metadata_class.metadata_format
            ):
                self.pop("swordMetadata", None)
                self.pop("swordMetadataSourceFormat", None)

            return None
        else:
            content_type, content_type_options = parse_options_header(content_type)

            # if isinstance(source, dict):
            assert issubclass(metadata_class, JSONMetadata)

            encoding = content_type_options.get("charset")
            if isinstance(encoding, str):
                metadata = metadata_class.from_document(
                    source, content_type=content_type, encoding=encoding,
                )
            else:
                metadata = metadata_class.from_document(
                    source, content_type=content_type,
                )

            if existing_metadata_object and not replace:
                with existing_metadata_object.file.storage().open() as existing_metadata_f:
                    existing_metadata = metadata_class.from_document(
                        existing_metadata_f, content_type=metadata_class.content_type,
                    )
                try:
                    metadata = existing_metadata + metadata
                except TypeError:
                    raise Conflict(
                        "Existing or new metadata is of wrong type for appending. Reconcile client-side and PUT instead"
                    )

            metadata_filename = self.metadata_key_prefix + metadata_class.filename

            if (
                isinstance(metadata, SWORDMetadata)
                or "swordMetadata" not in self
                or (
                    not isinstance(metadata, SWORDMetadata)
                    and self["swordMetadataSourceFormat"]
                    == metadata_class.metadata_format
                )
            ):
                metadata.update_record_metadata(self)
                self["swordMetadata"] = metadata.to_sword_metadata()
                self["swordMetadataSourceFormat"] = metadata_class.metadata_format

            object_version = ObjectVersion.create(
                bucket=self.bucket,
                key=metadata_filename,
                stream=io.BytesIO(bytes(metadata)),
            )
            ObjectVersionTag.create(
                object_version=object_version,
                key=ObjectTagKey.MetadataFormat.value,
                value=metadata_class.metadata_format,
            )

            return metadata


pid_resolver = Resolver(
    pid_type="depid",
    object_type="rec",
    getter=functools.partial(SWORDDeposit.get_record, with_deleted=True),
)
