import json
from http import HTTPStatus

from flask_security import url_for_security


def test_by_reference_deposit(api, users, location, es, remote_resource_server):
    with api.test_request_context(), api.test_client() as client:
        client.post(
            url_for_security("login"),
            data={"email": users[0]["email"], "password": "tester"},
        )

        response = client.post(
            "/sword/service-document",
            data=json.dumps(
                {
                    "byReferenceFiles": [
                        {
                            "@id": f"{remote_resource_server}/some-resource.json",
                            "contentDisposition": "attachment; filename=some-resource.json",
                            "contentType": "application/json",
                            "dereference": True,
                        }
                    ]
                }
            ),
            headers={
                "Content-Disposition": "attachment; by-reference=true",
                "Content-Type": "application/ld+json",
            },
        )
        assert response.status_code == HTTPStatus.CREATED
        assert response.is_json
