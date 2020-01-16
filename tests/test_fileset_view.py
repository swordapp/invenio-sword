import io
import time
from http import HTTPStatus

from flask import url_for
from flask_security import url_for_security
from invenio_db import db
from invenio_files_rest.models import ObjectVersion

from invenio_sword.api import SWORDDeposit


def test_get_fileset_url(api, users, location, es):
    with api.test_request_context(), api.test_client() as client:
        client.post(
            url_for_security("login"),
            data={"email": users[0]["email"], "password": "tester"},
        )
        record = SWORDDeposit.create({})
        record.commit()
        db.session.commit()

        time.sleep(1)

        response = client.get(
            url_for("invenio_sword.depid_fileset", pid_value=record.pid.pid_value)
        )
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


def test_put_fileset_url(api, users, location, es):
    with api.test_request_context(), api.test_client() as client:
        client.post(
            url_for_security("login"),
            data={"email": users[0]["email"], "password": "tester"},
        )
        record = SWORDDeposit.create({})
        record.commit()
        ObjectVersion.create(
            record.bucket,
            key="old-file.txt",
            stream=io.BytesIO(b"hello"),
            mimetype="text/plain",
        )
        db.session.commit()

        time.sleep(1)

        response = client.put(
            url_for("invenio_sword.depid_fileset", pid_value=record.pid.pid_value),
            data=b"hello again",
            headers={
                "Content-Disposition": "attachment; filename=new-file.txt",
                "Content-Type": "text/plain",
            },
        )
        assert response.status_code == HTTPStatus.NO_CONTENT

        # Check original ObjectVersion is marked deleted
        original_object_versions = list(
            ObjectVersion.query.filter_by(
                bucket=record.bucket, key="old-file.txt"
            ).order_by("created")
        )
        assert len(original_object_versions) == 2
        assert not original_object_versions[0].is_head
        assert original_object_versions[1].is_head
        assert original_object_versions[1].file is None

        # Check new object has been created
        new_object_version = ObjectVersion.query.filter_by(
            bucket=record.bucket, key="new-file.txt"
        ).one()
        assert new_object_version.is_head


def test_post_fileset_url(api, users, location, es):
    with api.test_request_context(), api.test_client() as client:
        client.post(
            url_for_security("login"),
            data={"email": users[0]["email"], "password": "tester"},
        )
        record = SWORDDeposit.create({})
        record.commit()
        ObjectVersion.create(
            record.bucket,
            key="old-file.txt",
            stream=io.BytesIO(b"hello"),
            mimetype="text/plain",
        )
        db.session.commit()

        time.sleep(1)

        response = client.post(
            url_for("invenio_sword.depid_fileset", pid_value=record.pid.pid_value),
            data=b"hello again",
            headers={
                "Content-Disposition": "attachment; filename=new-file.txt",
                "Content-Type": "text/plain",
            },
        )
        assert response.status_code == HTTPStatus.NO_CONTENT

        # Check original ObjectVersion is still there
        original_object_versions = list(
            ObjectVersion.query.filter_by(
                bucket=record.bucket, key="old-file.txt"
            ).order_by("created")
        )
        assert len(original_object_versions) == 1
        assert original_object_versions[0].is_head

        # Check new object has been created
        new_object_version = ObjectVersion.query.filter_by(
            bucket=record.bucket, key="new-file.txt"
        ).one()
        assert new_object_version.is_head
