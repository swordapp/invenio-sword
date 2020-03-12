import logging
import urllib.request
from typing import Iterable
from typing import Sequence
from typing import Union

import celery
from celery.result import AsyncResult
from invenio_db import db
from invenio_files_rest.models import ObjectVersion
from invenio_files_rest.models import ObjectVersionTag
from sqlalchemy import true

from invenio_sword.api import SWORDDeposit
from invenio_sword.enum import FileState
from invenio_sword.enum import ObjectTagKey
from invenio_sword.packaging import Packaging
from invenio_sword.utils import TagManager

logger = logging.getLogger(__name__)


@celery.shared_task
def dereference_object(record_id, version_id):
    object_version = ObjectVersion.query.filter(
        ObjectVersion.version_id == version_id
    ).one()
    if not object_version.is_head:
        logger.info(
            "Not fetching by-reference file (%s) because a newer version of the object now exists",
            object_version,
        )
        return

    if object_version.file_id:
        logger.warning("File has already been dereferenced (%s)", object_version)
        return [object_version.key]

    tags = TagManager(object_version)

    if ObjectTagKey.ByReferenceURL not in tags:
        logger.error("Cannot fetch by-reference file (%s) without URL", object_version)
        raise ValueError(
            "Missing URL for by-reference file {!r}".format(object_version)
        )

    try:
        tags[ObjectTagKey.FileState] = FileState.Downloading

        response = urllib.request.urlopen(tags[ObjectTagKey.ByReferenceURL])
        object_version.set_contents(response)
        tags[ObjectTagKey.FileState] = FileState.Pending
        del tags[ObjectTagKey.ByReferenceNotDeleted]
        return [object_version.key]
    except Exception:
        logger.exception("Error retrieving by-reference file")
        tags[ObjectTagKey.FileState] = FileState.Error
        raise
    finally:
        db.session.commit()


@celery.shared_task
def unpack_object(record_id, version_id):
    record = SWORDDeposit.get_record(record_id)

    object_version: ObjectVersion = ObjectVersion.query.filter(
        ObjectVersion.version_id == version_id
    ).one()
    if not object_version.is_head:
        logger.info(
            "Not fetching by-reference file (%s) because a newer version of the object now exists",
            object_version,
        )
        return

    tags = TagManager(object_version)

    try:
        packaging = Packaging.for_record_and_name(record, tags[ObjectTagKey.Packaging])
        keys = packaging.unpack(object_version)
        tags[ObjectTagKey.FileState] = FileState.Ingested
        return [object_version.key] + list(keys)
    except Exception:
        logger.exception(
            "Failed to unpack %s:%s", object_version.bucket_id, object_version.key
        )
        tags[ObjectTagKey.FileState] = FileState.Error
        raise
    finally:
        db.session.commit()


@celery.shared_task
def delete_old_objects(
    ignore_keys: Union[Sequence[AsyncResult], Iterable[str]] = (), *, bucket_id: str
):
    for object_version in ObjectVersion.query.join(ObjectVersionTag).filter(
        ObjectVersion.bucket_id == bucket_id,
        ObjectVersion.key.notin_(ignore_keys),
        ObjectVersion.is_head == true(),
        ObjectVersionTag.key.in_(
            [
                ObjectTagKey.FileSetFile.value,
                ObjectTagKey.DerivedFrom.value,
                ObjectTagKey.OriginalDeposit.value,
            ]
        ),
    ):
        if object_version.file_id:
            # Delete any extant files
            ObjectVersion.delete(object_version.bucket, object_version.key)
        else:
            # Delete any tags that say that an ObjectVersion is a yet-to-be-dereferenced file
            ObjectVersionTag.query.filter(
                ObjectVersionTag.version_id == object_version.version_id,
                ObjectVersionTag.key == ObjectTagKey.ByReferenceNotDeleted.value,
                ObjectVersionTag.value == "true",
            ).delete()

    db.session.commit()
