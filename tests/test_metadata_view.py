import http.client
import json
import time

import pytest
from flask import url_for
from flask_security import url_for_security
from invenio_db import db

from invenio_sword.api import SWORDDeposit
from invenio_sword.metadata import SWORDMetadata


def test_get_metadata_document(api, users, location, es):
    with api.test_request_context(), api.test_client() as client:
        client.post(
            url_for_security("login"),
            data={"email": users[0]["email"], "password": "tester"},
        )

        record = SWORDDeposit.create({})
        record.sword_metadata = SWORDMetadata({"dc:title": "Deposit title"})
        record.commit()
        db.session.commit()
        time.sleep(1)

        response = client.get("/sword/deposit/{}".format(record.pid.pid_value))
        assert response.status_code == 200

        response = client.get("/sword/deposit/{}/metadata".format(record.pid.pid_value))
        assert response.status_code == 200
        assert response.is_json
        assert (
            response.headers["Metadata-Format"]
            == "http://purl.org/net/sword/3.0/types/Metadata"
        )
        assert response.json == {
            "@id": "http://localhost/sword/deposit/{}/metadata".format(
                record.pid.pid_value
            ),
            "dc:title": "Deposit title",
        }


def test_get_metadata_document_when_not_available(api, users, location, es):
    with api.test_request_context(), api.test_client() as client:
        client.post(
            url_for_security("login"),
            data={"email": users[0]["email"], "password": "tester"},
        )
        record = SWORDDeposit.create({})
        record.commit()
        db.session.commit()
        time.sleep(1)

        status_response = client.get("/sword/deposit/{}".format(record.pid.pid_value))
        assert status_response.status_code == http.client.OK
        status_response = client.get(
            "/sword/deposit/{}/metadata".format(record.pid.pid_value)
        )
        assert status_response.status_code == http.client.NOT_FOUND


def test_put_metadata_document_without_body(api, users, location, es):
    with api.test_request_context(), api.test_client() as client:
        client.post(
            url_for_security("login"),
            data={"email": users[0]["email"], "password": "tester"},
        )
        record = SWORDDeposit.create({})
        record.commit()
        db.session.commit()
        time.sleep(1)

        response = client.put("/sword/deposit/{}/metadata".format(record.pid.pid_value))
        assert response.status_code == http.client.UNSUPPORTED_MEDIA_TYPE


def test_put_metadata_document_invalid_json(api, users, location, es):
    with api.test_request_context(), api.test_client() as client:
        client.post(
            url_for_security("login"),
            data={"email": users[0]["email"], "password": "tester"},
        )
        record = SWORDDeposit.create({})
        record.commit()
        db.session.commit()
        time.sleep(1)

        response = client.put(
            "/sword/deposit/{}/metadata".format(record.pid.pid_value),
            headers={
                "Content-Type": "application/ld+json",
                "Metadata-Format": "http://purl.org/net/sword/3.0/types/Metadata",
            },
        )
        assert response.status_code == http.client.BAD_REQUEST


def test_put_metadata_document(api, users, location, es):
    with api.test_request_context(), api.test_client() as client:
        client.post(
            url_for_security("login"),
            data={"email": users[0]["email"], "password": "tester"},
        )
        record = SWORDDeposit.create({})
        record.commit()
        db.session.commit()
        time.sleep(1)

        response = client.put(
            "/sword/deposit/{}/metadata".format(record.pid.pid_value),
            headers={
                "Metadata-Format": "http://purl.org/net/sword/3.0/types/Metadata",
                "Content-Type": "application/ld+json",
            },
            data=json.dumps({}),
        )
        assert response.status_code == http.client.NO_CONTENT

        record = SWORDDeposit.get_record(record.id)
        assert (
            record.sword_metadata_format
            == "http://purl.org/net/sword/3.0/types/Metadata"
        )
        assert isinstance(record.sword_metadata, SWORDMetadata)
        assert record.sword_metadata.data == {}


@pytest.mark.parametrize(
    "view_name,status_code,additional_headers",
    [
        ("invenio_sword.depid_deposit_metadata", http.client.NO_CONTENT, {}),
        (
            "invenio_sword.depid_deposit_status",
            http.client.OK,
            {"Content-Disposition": "attachment; metadata=true"},
        ),
    ],
)
def test_post_metadata_document_to_append(
    api, users, location, es, view_name, status_code, additional_headers
):
    with api.test_request_context(), api.test_client() as client:
        client.post(
            url_for_security("login"),
            data={"email": users[0]["email"], "password": "tester"},
        )
        record = SWORDDeposit.create({})
        record.sword_metadata = SWORDMetadata(
            {
                "@context": "https://swordapp.github.io/swordv3/swordv3.jsonld",
                "dc:title": "Some title",
                "dc:subject": "Some subject",
            }
        )
        record.commit()
        db.session.commit()
        time.sleep(1)

        response = client.post(
            url_for(view_name, pid_value=record.pid.pid_value),
            headers={
                "Metadata-Format": "http://purl.org/net/sword/3.0/types/Metadata",
                "Content-Type": "application/ld+json",
                **additional_headers,
            },
            data=json.dumps(
                {
                    "@context": "https://swordapp.github.io/swordv3/swordv3.jsonld",
                    "dc:subject": "Another subject",
                    "dc:creator": "A person",
                }
            ),
        )
        assert response.status_code == status_code

        record = SWORDDeposit.get_record(record.id)
        assert (
            record.sword_metadata_format
            == "http://purl.org/net/sword/3.0/types/Metadata"
        )
        assert isinstance(record.sword_metadata, SWORDMetadata)
        assert record.sword_metadata.data == {
            "@context": "https://swordapp.github.io/swordv3/swordv3.jsonld",
            "dc:title": "Some title",
            "dc:subject": "Another subject",
            "dc:creator": "A person",
        }


def test_put_metadata_document_with_unsupported_format(api, users, location, es):
    with api.test_request_context(), api.test_client() as client:
        client.post(
            url_for_security("login"),
            data={"email": users[0]["email"], "password": "tester"},
        )
        record = SWORDDeposit.create({})
        record.commit()
        db.session.commit()
        time.sleep(1)

        response = client.put(
            "/sword/deposit/{}/metadata".format(record.pid.pid_value),
            headers={
                "Metadata-Format": "http://sword.invalid/Metadata",
                "Content-Type": "application/ld+json",
            },
            data=json.dumps({}),
        )
        assert response.status_code == http.client.NOT_IMPLEMENTED


def test_delete_metadata_document(api, users, location, es):
    with api.test_request_context(), api.test_client() as client:
        client.post(
            url_for_security("login"),
            data={"email": users[0]["email"], "password": "tester"},
        )
        record = SWORDDeposit.create({})
        record.sword_metadata = SWORDMetadata({"dc:title": "Deposit title"})
        record.commit()
        db.session.commit()
        time.sleep(1)

        assert record.sword_metadata_format is not None
        assert record.sword_metadata is not None

        response = client.delete(
            "/sword/deposit/{}/metadata".format(record.pid.pid_value)
        )
        assert response.status_code == http.client.NO_CONTENT

        record = SWORDDeposit.get_record(record.id)
        assert record.sword_metadata_format is None
        assert record.sword_metadata is None
