import http.client
import json

from invenio_db import db

from invenio_sword.api import SWORDDeposit
from invenio_sword.metadata import SWORDMetadata


def test_get_metadata_document(api, location):
    record = SWORDDeposit.create({})
    record.sword_metadata = SWORDMetadata({"dc:title": "Deposit title"})
    record.commit()
    db.session.commit()

    with api.test_client() as client:
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


def test_get_metadata_document_when_not_available(api, location):
    record = SWORDDeposit.create({})

    with api.test_client() as client:
        status_response = client.get("/sword/deposit/{}".format(record.pid.pid_value))
        assert status_response.status_code == http.client.OK
        status_response = client.get(
            "/sword/deposit/{}/metadata".format(record.pid.pid_value)
        )
        assert status_response.status_code == http.client.NOT_FOUND


def test_put_metadata_document_without_body(api, location):
    record = SWORDDeposit.create({})

    with api.test_client() as client:
        response = client.put("/sword/deposit/{}/metadata".format(record.pid.pid_value))
        assert response.status_code == http.client.BAD_REQUEST


def test_put_metadata_document(api, location):
    record = SWORDDeposit.create({})

    with api.test_client() as client:
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
        record.sword_metadata_format == "http://purl.org/net/sword/3.0/types/Metadata"
    )
    assert isinstance(record.sword_metadata, SWORDMetadata)
    assert record.sword_metadata.data == {}


def test_put_metadata_document_with_unsupported_format(api, location):
    record = SWORDDeposit.create({})

    with api.test_client() as client:
        response = client.put(
            "/sword/deposit/{}/metadata".format(record.pid.pid_value),
            headers={
                "Metadata-Format": "http://sword.invalid/Metadata",
                "Content-Type": "application/ld+json",
            },
            data=json.dumps({}),
        )
        assert response.status_code == http.client.NOT_IMPLEMENTED


def test_delete_metadata_document(api, location):
    record = SWORDDeposit.create({})
    record.sword_metadata = SWORDMetadata({"dc:title": "Deposit title"})
    record.commit()
    db.session.commit()

    assert record.sword_metadata_format is not None
    assert record.sword_metadata is not None

    with api.test_client() as client:
        response = client.delete(
            "/sword/deposit/{}/metadata".format(record.pid.pid_value)
        )
        assert response.status_code == http.client.NO_CONTENT

    record = SWORDDeposit.get_record(record.id)
    assert record.sword_metadata_format is None
    assert record.sword_metadata is None
