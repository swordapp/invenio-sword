import functools
from enum import Enum
from typing import Dict, Callable, Any
from typing import Mapping
from typing import Union

import sqlalchemy.orm.session
from invenio_db import db
from sqlalchemy import event

from invenio_files_rest.models import ObjectVersion
from invenio_files_rest.models import ObjectVersionTag
from invenio_sword.enum import FileState
from invenio_sword.enum import ObjectTagKey


class TagManager(Dict[ObjectTagKey, Union[str, Enum]]):
    enum_keys = {
        ObjectTagKey.FileState: FileState,
    }

    def __init__(self, object_version: ObjectVersion):
        self._object_version = object_version
        super().__init__(
            {
                ObjectTagKey(key): self.enum_keys.get(ObjectTagKey(key), str)(value)
                for key, value in self._object_version.get_tags().items()
            }
        )

    def __setitem__(self, key: ObjectTagKey, value: Union[str, Enum]):  # type: ignore
        super().__setitem__(key, self.enum_keys.get(ObjectTagKey(key), str)(value))
        if key in self.enum_keys:
            # Check this is a valid value
            self.enum_keys[key](value)
        if isinstance(value, Enum):
            value = value.value
        ObjectVersionTag.create_or_update(self._object_version, key.value, value)

    def __delitem__(self, key: ObjectTagKey):  # type: ignore
        ObjectVersionTag.delete(self._object_version, key.value)
        super().pop(key, None)

    def update(  # type: ignore
        self,
        __m: Mapping[ObjectTagKey, Union[str, Enum]] = None,
        **kwargs: Union[str, Enum]
    ) -> None:
        for mapping_key, value in (__m or {}).items():
            self[mapping_key] = value
        for kwargs_key, value in kwargs.items():
            self[ObjectTagKey(kwargs_key)] = value


# Functionality to execute functions once a session has been committed, ensuring that data in the database is available
# to other processes, e.g. a celery worker

_after_commit_callback_session_info_key = "invenio-sword-after-commit-callbacks"


def register_after_commit_callback(_callback: Callable[[], Any], *args, **kwargs):
    # Should only be called within a transaction
    assert db.session.is_active
    if args or kwargs:
        _callback = functools.partial(_callback, *args, **kwargs)
    try:
        db.session.info[_after_commit_callback_session_info_key].append(_callback)
    except KeyError:
        db.session.info[_after_commit_callback_session_info_key] = [_callback]


@event.listens_for(db.session, "after_commit")
def session_after_commit_hook(session: sqlalchemy.orm.session.Session):
    for callback in session.info.pop(_after_commit_callback_session_info_key, ()):
        callback()
