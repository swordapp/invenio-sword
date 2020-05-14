from __future__ import annotations

import mimetypes
import typing
import uuid
from typing import Collection
from typing import Union

from flask import current_app
from invenio_db import db

from invenio_files_rest.models import ObjectVersion
from ..enum import ObjectTagKey, FileState
from ..utils import TagManager

if typing.TYPE_CHECKING:  # pragma: nocover
    from ..api import SWORDDeposit


class Packaging:
    packaging_name: str

    def __init__(self, record: SWORDDeposit):
        self.record = record

    def get_original_deposit_filename(
        self, filename: str = None, media_type: str = None
    ) -> str:
        if filename:
            return filename
        elif media_type and mimetypes.guess_extension(media_type):
            return "{}{}".format(uuid.uuid4(), mimetypes.guess_extension(media_type))
        else:
            return "{}.bin".format(uuid.uuid4())

    @classmethod
    def for_record_and_name(cls, record: SWORDDeposit, packaging_name: str):
        packaging_class = current_app.config["SWORD_ENDPOINTS"][record.pid.pid_type][
            "packaging_formats"
        ][packaging_name]
        return packaging_class(record)

    def shortcut_unpack(
        self, object_version: ObjectVersion
    ) -> Union[NotImplemented, Collection[str]]:
        """Override this to shortcut task-based unpacking"""
        return NotImplemented

    def unpack(self, object_version: ObjectVersion) -> Collection[str]:
        raise NotImplementedError  # pragma: nocover

    def get_file_list(self, object_version: ObjectVersion) -> Collection[str]:
        raise NotImplementedError  # pragma: nocover

    def _set_file_content(self, key: str, media_type: str, stream):
        object_version = ObjectVersion.query.filter(
            ObjectVersion.bucket == self.record.bucket,
            ObjectVersion.key == key,
            ObjectVersion.file_id.is_(None),
        ).first()
        if object_version:
            object_version.mimetype = media_type
            object_version.set_contents(stream)
            db.session.add(object_version)
        else:
            object_version = ObjectVersion.create(
                self.record.bucket,
                key,
                mimetype=mimetypes.guess_type(key)[0],
                stream=stream,
            )

        tags = TagManager(object_version)
        tags[ObjectTagKey.FileState] = FileState.Ingested
        del tags[ObjectTagKey.NotDeleted]
