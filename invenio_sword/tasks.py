import logging
import urllib.request

import celery
from invenio_files_rest.models import ObjectVersion
from sword3common.constants import PackagingFormat

from invenio_sword.enum import FileState
from invenio_sword.enum import ObjectTagKey
from invenio_sword.utils import TagManager

logger = logging.getLogger(__name__)


@celery.shared_task
def fetch_by_reference_file(version_id):
    object_version = ObjectVersion.query.filter(
        ObjectVersion.version_id == version_id
    ).one()
    if not object_version.is_head:
        logger.info(
            "Not fetching by-reference file (%s) because a newer version of the object now exists",
            object_version,
        )
        return

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

        if tags[ObjectTagKey.Packaging] == PackagingFormat.Binary:
            tags[ObjectTagKey.FileState] = FileState.Ingested
        else:
            tags[ObjectTagKey.FileState] = FileState.Unpacking
            unpack_object.delay(object_version.version_id)
    except Exception:
        logger.exception("Error retrieving by-reference file")
        tags[ObjectTagKey.FileState] = FileState.Error
        raise


@celery.shared_task
def unpack_object(version_id):
    pass
