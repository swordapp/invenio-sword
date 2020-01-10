import os
import time
from http import HTTPStatus

from flask_security import url_for_security
from invenio_db import db

from invenio_sword.api import SWORDDeposit
from invenio_sword.packaging import SWORDBagItPackaging


def create_bagit_record(fixtures_path):
    with open(os.path.join(fixtures_path, "bagit.zip"), "rb") as f:
        record = SWORDDeposit.create({})
        SWORDBagItPackaging().ingest(
            record=record, stream=f, content_type="application/zip",
        )
        record.commit()
        db.session.commit()
    return record


def test_file_get(fixtures_path, location, es, api, users):
    with api.test_request_context(), api.test_client() as client:
        client.post(
            url_for_security("login"),
            data={"email": users[0]["email"], "password": "tester"},
        )

        bagit_record = create_bagit_record(fixtures_path)

        status_document = bagit_record.get_status_as_jsonld()
        assert len(status_document["links"]) > 0

        time.sleep(1)

        for link in status_document["links"]:
            response = client.get(link["@id"])
            assert response.status_code == HTTPStatus.OK
