from __future__ import annotations

import functools
import io
import json
import logging
import typing

from flask import url_for
from invenio_deposit.api import Deposit
from invenio_deposit.api import has_status
from invenio_files_rest.models import ObjectVersion
from invenio_files_rest.models import ObjectVersionTag
from invenio_pidstore.resolver import Resolver
from invenio_records_files.api import FileObject
from sqlalchemy import true
from sword3common.constants import DepositState
from sword3common.constants import FileState
from sword3common.constants import Rel
from werkzeug.exceptions import Conflict
from werkzeug.http import parse_options_header

from .metadata import Metadata
from invenio_sword.enum import ObjectTagKey
from invenio_sword.metadata import SWORDMetadata
from invenio_sword.packaging import IngestResult
from invenio_sword.packaging import Packaging
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
        editable = self["_deposit"].get("status") == "draft"

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
                "appendMetadata": editable,
                "appendFiles": editable,
                "replaceMetadata": editable,
                "replaceFiles": editable,
                "deleteMetadata": editable,
                "deleteFiles": editable,
                "deleteObject": editable,
            },
            "links": self.links,
        }

    @property
    def links(self):

        links = []
        for file in self.files or ():
            link = {
                "@id": file.rest_file_url,
                "contentType": file.obj.mimetype,
                "status": FileState.Ingested,
            }

            tags = {tag.key: tag.value for tag in file.tags}
            rel = set()
            if tags.get(ObjectTagKey.OriginalDeposit.value) == "true":
                rel.add(Rel.OriginalDeposit)
            if tags.get(ObjectTagKey.FileSetFile.value) == "true":
                rel.add(Rel.FileSetFile)
            derived_from = tags.get(ObjectTagKey.DerivedFrom.value)
            if derived_from:
                rel.add(Rel.DerivedResource)
                link["derivedFrom"] = url_for(
                    "invenio_sword.{}_file".format(self.pid.pid_type),
                    pid_value=self.pid.pid_value,
                    key=derived_from,
                    _external=True,
                )
            if ObjectTagKey.Packaging.value in tags:
                link["packaging"] = tags[ObjectTagKey.Packaging.value]
            if ObjectTagKey.MetadataFormat.value in tags:
                rel.add(Rel.FormattedMetadata)
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
                    "@id": DepositState.InProgress,
                    "description": "the item is currently inProgress",
                }
            )
        elif self["_deposit"].get("status") == "published":
            states.append(
                {"@id": DepositState.Ingested, "description": "the item is ingested",}
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

    @has_status(status="draft")
    def set_fileset_from_stream(
        self,
        stream: typing.Optional[BytesReader],
        packaging_class: typing.Type[Packaging],
        content_disposition: str = None,
        content_type: str = None,
        replace=True,
    ) -> IngestResult:
        if stream:
            content_disposition, content_disposition_options = parse_options_header(
                content_disposition or ""
            )
            content_type, _ = parse_options_header(content_type or "")
            filename = content_disposition_options.get("filename")
            ingest_result: IngestResult = packaging_class().ingest(
                record=self,
                stream=stream,
                filename=filename,
                content_type=content_type,
            )
        else:
            ingest_result = IngestResult(None)

        if replace:
            ingested_keys = [
                object_version.key for object_version in ingest_result.ingested_objects
            ]
            # Remove previous objects associated with filesets, including original deposits, and anything that was
            # derived from them
            for object_version in (
                ObjectVersion.query.join(ObjectVersionTag)
                .filter(
                    ObjectVersion.bucket == self.bucket,
                    ObjectVersion.is_head == true(),
                    ObjectVersion.file_id.isnot(None),
                    ObjectVersion.key.notin_(ingested_keys),
                    ObjectVersionTag.key.in_(
                        [
                            ObjectTagKey.FileSetFile.value,
                            ObjectTagKey.DerivedFrom.value,
                            ObjectTagKey.OriginalDeposit.value,
                        ]
                    ),
                )
                .distinct(ObjectVersion.key)
            ):
                ObjectVersion.delete(self.bucket, object_version.key)

        return ingest_result

    @has_status(status="draft")
    def set_metadata(
        self,
        source: typing.Optional[typing.Union[BytesReader, dict]],
        metadata_class: typing.Type[Metadata],
        content_type: str = None,
        derived_from: str = None,
        replace: bool = True,
    ) -> typing.Optional[Metadata]:
        if isinstance(source, dict):
            source = io.BytesIO(json.dumps(source).encode("utf-8"))

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
            if derived_from:
                ObjectVersionTag.create(
                    object_version=object_version,
                    key=ObjectTagKey.DerivedFrom.value,
                    value=derived_from,
                )

            return metadata

    def set_by_reference_files(self, by_reference_files, replace=True):
        object_versions = []
        for by_reference_file in by_reference_files:
            content_disposition, content_disposition_options = parse_options_header(
                by_reference_file["contentDisposition"],
            )
            content_type, _ = parse_options_header(by_reference_file["contentType"])
            filename = content_disposition_options["filename"]
            object_version = ObjectVersion.create(
                self.bucket, filename, mimetype=content_type
            )
            ObjectVersionTag.create(
                object_version=object_version,
                key=ObjectTagKey.ByReferenceURL.value,
                value=by_reference_file["@id"],
            )
            ObjectVersionTag.create(
                object_version=object_version,
                key=ObjectTagKey.ByReferenceDereference.value,
                value="true" if by_reference_file["dereference"] else "false",
            )
            if "ttl" in by_reference_file:
                ObjectVersionTag.create(
                    object_version=object_version,
                    key=ObjectTagKey.ByReferenceTTL.value,
                    value=by_reference_file["ttl"],
                )
            if "contentLength" in by_reference_file:
                ObjectVersionTag.create(
                    object_version=object_version,
                    key=ObjectTagKey.ByReferenceContentLength.value,
                    value=str(by_reference_file["contentLength"]),
                )
            object_versions.append(object_version)

        return IngestResult(original_deposit=None, unpackaged_objects=object_versions)


pid_resolver = Resolver(
    pid_type="depid",
    object_type="rec",
    getter=functools.partial(SWORDDeposit.get_record, with_deleted=True),
)
