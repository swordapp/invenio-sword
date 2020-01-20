import io
from http import HTTPStatus

from flask_security import url_for_security
from invenio_db import db
from invenio_files_rest.models import ObjectVersion

from invenio_sword.api import SWORDDeposit


def test_get_status_document_not_found(api, location, es):
    with api.app_context(), api.test_client() as client:
        response = client.get("/sword/deposit/1234")
        assert response.status_code == HTTPStatus.NOT_FOUND


def test_get_status_document(api, users, location, es):
    with api.test_request_context(), api.test_client() as client:
        client.post(
            url_for_security("login"),
            data={"email": users[0]["email"], "password": "tester"},
        )
        record = SWORDDeposit.create({})
        record.commit()
        db.session.commit()

        ObjectVersion.create(
            record.bucket,
            "file.n3",
            mimetype="text/n3",
            stream=io.BytesIO(b"1 _:a 2 ."),
        )

        response = client.get("/sword/deposit/{}".format(record.pid.pid_value))
        assert response.status_code == HTTPStatus.OK
        assert len(response.json["links"]) == 1
        assert response.json["links"][0]["contentType"] == "text/n3"


def test_put_status_document(api, users, location, es):
    with api.test_request_context(), api.test_client() as client:
        client.post(
            url_for_security("login"),
            data={"email": users[0]["email"], "password": "tester"},
        )
        record = SWORDDeposit.create({})
        record.commit()
        db.session.commit()

        ObjectVersion.create(
            record.bucket,
            "file.n3",
            mimetype="text/n3",
            stream=io.BytesIO(b"1 _:a 2 ."),
        )

        response = client.put(
            "/sword/deposit/{}".format(record.pid.pid_value), data=b""
        )
        assert response.status_code == HTTPStatus.OK

        # This should have removed the previous file, as the empty PUT is a reset.
        object_versions = list(
            ObjectVersion.query.filter_by(bucket=record.bucket).order_by("created")
        )
        assert len(object_versions) == 2
        assert not object_versions[0].is_head
        assert object_versions[1].is_head
        assert object_versions[1].file is None
