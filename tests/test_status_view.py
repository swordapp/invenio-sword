import http.client
import io

from invenio_files_rest.models import ObjectVersion

from invenio_sword.api import SWORDDeposit


def test_get_status_document_not_found(api, location):
    with api.app_context(), api.test_client() as client:
        response = client.get("/sword/deposit/1234")
        assert response.status_code == http.client.NOT_FOUND


def test_get_status_document(api, location):
    with api.app_context(), api.test_client() as client:
        record = SWORDDeposit.create({})
        ObjectVersion.create(
            record.bucket,
            "file.n3",
            mimetype="text/n3",
            stream=io.BytesIO(b"1 _:a 2 ."),
        )

        response = client.get("/sword/deposit/{}".format(record.pid.pid_value))
        assert response.status_code == http.client.OK
        assert len(response.json["links"]) == 1
        assert response.json["links"][0]["contentType"] == "text/n3"
