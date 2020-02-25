import json
import unittest.mock
from http import HTTPStatus

import pytest
from flask_security import url_for_security
from invenio_files_rest.models import Bucket
from invenio_files_rest.models import ObjectVersion
from sword3common.constants import JSON_LD_CONTEXT


@pytest.mark.parametrize(
    "data,fields_with_errors, fields_without_errors",
    [
        # Missing fields
        ({}, ["@context", "@type", "byReferenceFiles"], []),
        # Wrong @context value
        ({"@context": "http://example.com/"}, ["@context"], []),
        # Correct @context value
        ({"@context": JSON_LD_CONTEXT}, [], ["@context"]),
        # Wrong @type value
        ({"@type": "Metadata"}, ["@type"], []),
        # Correct @type value
        ({"@type": "ByReference"}, [], ["@type"]),
        # Missing fields in byReferenceFiles
        ({"byReferenceFiles": [{}]}, ["byReferenceFiles"], []),
    ],
)
def test_by_reference_validation(
    api, users, location, es, data, fields_with_errors, fields_without_errors
):
    with api.test_request_context(), api.test_client() as client:
        client.post(
            url_for_security("login"),
            data={"email": users[0]["email"], "password": "tester"},
        )

        response = client.post(
            "/sword/service-document",
            data=json.dumps(data),
            headers={
                "Content-Disposition": "attachment; by-reference=true",
                "Content-Type": "application/ld+json",
            },
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.is_json
        assert response.json["@type"] == "ValidationFailed"
        # The fields with errors are the superset of the ones we expected; i.e. it shouldn't accept data we
        # in this test know is wrong
        print(response.json)
        assert set(response.json["errors"]) >= set(fields_with_errors)
        # We know these fields to be good
        assert not (set(response.json["errors"]) & set(fields_without_errors))


def test_by_reference_deposit(api, users, location, es, remote_resource_server):
    with api.test_request_context(), api.test_client() as client, unittest.mock.patch(
        "invenio_sword.tasks.fetch_by_reference_file"
    ) as fetch_by_reference_file:
        client.post(
            url_for_security("login"),
            data={"email": users[0]["email"], "password": "tester"},
        )

        response = client.post(
            "/sword/service-document",
            data=json.dumps(
                {
                    "@context": JSON_LD_CONTEXT,
                    "@type": "ByReference",
                    "byReferenceFiles": [
                        {
                            "@id": f"{remote_resource_server}/some-resource.json",
                            "contentDisposition": "attachment; filename=some-resource.json",
                            "contentType": "application/json",
                            "dereference": True,
                        }
                    ],
                }
            ),
            headers={
                "Content-Disposition": "attachment; by-reference=true",
                "Content-Type": "application/ld+json",
            },
        )
        assert response.status_code == HTTPStatus.CREATED
        assert response.is_json

        bucket = Bucket.query.one()
        object_version: ObjectVersion = ObjectVersion.query.filter(
            ObjectVersion.bucket == bucket
        ).one()

        fetch_by_reference_file.delay.assert_called_once_with(object_version.version_id)
