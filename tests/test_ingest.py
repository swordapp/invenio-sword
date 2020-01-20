import os
from http import HTTPStatus

import pytest
from flask_security import url_for_security

original_deposit = (
    object()
)  # A sentinel, representing the original deposit in our expected data

packaged_content = {
    "example.svg": {
        "rel": [
            "http://purl.org/net/sword/3.0/terms/derivedResource",
            "http://purl.org/net/sword/3.0/terms/fileSetFile",
        ],
        "contentType": "image/svg+xml",
        "status": "http://purl.org/net/sword/3.0/filestate/ingested",
        "derivedFrom": original_deposit,
    },
    "hello.txt": {
        "rel": [
            "http://purl.org/net/sword/3.0/terms/derivedResource",
            "http://purl.org/net/sword/3.0/terms/fileSetFile",
        ],
        "contentType": "text/plain",
        "status": "http://purl.org/net/sword/3.0/filestate/ingested",
        "derivedFrom": original_deposit,
    },
}


@pytest.mark.parametrize(
    "filename,packaging,content_type,expected_links",
    [
        # A binary deposit
        (
            "binary.svg",
            "http://purl.org/net/sword/3.0/package/Binary",
            "image/svg+xml",
            {
                "binary.svg": {
                    "rel": [
                        "http://purl.org/net/sword/3.0/terms/fileSetFile",
                        "http://purl.org/net/sword/3.0/terms/originalDeposit",
                    ],
                    "contentType": "image/svg+xml",
                    "status": "http://purl.org/net/sword/3.0/filestate/ingested",
                }
            },
        ),
        # A simple zip deposit
        (
            "simple.zip",
            "http://purl.org/net/sword/3.0/package/SimpleZip",
            "application/zip",
            {
                original_deposit: {
                    "rel": ["http://purl.org/net/sword/3.0/terms/originalDeposit"],
                    "contentType": "application/zip",
                    "status": "http://purl.org/net/sword/3.0/filestate/ingested",
                    "packaging": "http://purl.org/net/sword/3.0/package/SimpleZip",
                },
                **packaged_content,  # type: ignore
            },
        ),
        # A BagIt deposit
        (
            "bagit.zip",
            "http://purl.org/net/sword/3.0/package/SWORDBagIt",
            "application/zip",
            {
                original_deposit: {
                    "rel": ["http://purl.org/net/sword/3.0/terms/originalDeposit"],
                    "contentType": "application/zip",
                    "status": "http://purl.org/net/sword/3.0/filestate/ingested",
                    "packaging": "http://purl.org/net/sword/3.0/package/SWORDBagIt",
                },
                **packaged_content,  # type: ignore
            },
        ),
    ],
)
def test_ingest(
    api,
    users,
    location,
    es,
    fixtures_path,
    filename,
    packaging,
    content_type,
    expected_links,
):
    with api.test_request_context(), api.test_client() as client:
        client.post(
            url_for_security("login"),
            data={"email": users[0]["email"], "password": "tester"},
        )

        with open(os.path.join(fixtures_path, filename), "rb") as f:
            response = client.post(
                "/sword/service-document",
                data=f,
                headers={
                    "Packaging": packaging,
                    "Content-Type": content_type,
                    "Content-Disposition": "attachment; filename={}".format(filename),
                },
            )
        assert response.status_code == HTTPStatus.CREATED

        response = client.get(response.headers["Location"])

        for link in response.json["links"]:
            print(link)
            key = link["@id"].split("/", 7)[-1]
            if (
                "http://purl.org/net/sword/3.0/terms/originalDeposit" in link["rel"]
                and "http://purl.org/net/sword/3.0/terms/fileSetFile" not in link["rel"]
            ):
                expected_link = expected_links[original_deposit]
            else:
                expected_link = expected_links[key]

            if "derivedFrom" in link:
                link["derivedFrom"] = original_deposit

            expected_link["@id"] = response.json["@id"] + "/file/" + key

            assert expected_link == link

        assert len(response.json["links"]) == len(expected_links)
