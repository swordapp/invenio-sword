import http.client

from flask import Blueprint
from flask import current_app
from flask import redirect
from flask import request
from flask import Response
from invenio_db import db
from invenio_records_rest.views import pass_record
from invenio_rest import ContentNegotiatedMethodView
from werkzeug.exceptions import BadRequest
from werkzeug.http import parse_options_header

from . import serializers
from .api import SWORDDeposit


class ServiceDocumentView(ContentNegotiatedMethodView):
    def get(self):
        return {
            "@type": "ServiceDocument",
            "dc:title": current_app.config["THEME_SITENAME"],
            "root": request.url,
            "acceptDeposits": True,
            "version": "http://purl.org/net/sword/3.0",
            "maxUploadSize": current_app.config["SWORD_MAX_UPLOAD_SIZE"],
            "maxByReferenceSize": current_app.config["SWORD_MAX_BY_REFERENCE_SIZE"],
            "acceptPackaging": sorted(current_app.config["SWORD_PACKAGING_FORMATS"]),
            "acceptMetadata": sorted(current_app.config["SWORD_METADATA_FORMATS"]),
        }

    def post(self):
        content_disposition, content_disposition_options = parse_options_header(
            request.headers.get("Content-Disposition", "")
        )
        content_type, _ = parse_options_header(request.content_type)
        filename = content_disposition_options.get("filename")
        in_progress = request.headers.get("In-Progress") == "true"
        packaging = request.headers.get(
            "Packaging", current_app.config["SWORD_DEFAULT_PACKAGING_FORMAT"]
        )

        try:
            packaging = current_app.config["SWORD_PACKAGING_FORMATS"][packaging]()
        except KeyError:
            raise BadRequest("Unexpected packaging format")

        # print(request.files)
        record = SWORDDeposit.create(
            {"status": "draft" if in_progress else "published",}
        )

        packaging.ingest(
            record=record,
            stream=request.stream,
            filename=filename,
            content_type=content_type,
        )

        record.commit()
        db.session.commit()

        response = self.make_response(record.get_status_as_jsonld())  # type: Response
        response.status_code = http.client.CREATED
        response.headers["Location"] = record.sword_api_url
        return response


class DepositStatusView(ContentNegotiatedMethodView):
    @pass_record
    def get(self, pid, record: SWORDDeposit):
        return record.get_status_as_jsonld()


class DepositMetadataView(ContentNegotiatedMethodView):
    @pass_record
    def get(self, pid, record: SWORDDeposit):
        raise NotImplementedError


class DepositFilesetView(ContentNegotiatedMethodView):
    @pass_record
    def get(self, pid, record: SWORDDeposit):
        raise NotImplementedError


_PID = 'pid(depid,record_class="invenio_sword.api:SWORDDeposit")'


def create_blueprint(prefix="/sword"):
    blueprint = Blueprint("invenio_sword", __name__, url_prefix="",)

    blueprint.add_url_rule(
        prefix + "/service-document",
        endpoint="service-document",
        view_func=ServiceDocumentView.as_view(
            "service",
            serializers={"application/ld+json": serializers.jsonld_serializer,},
        ),
    )

    blueprint.add_url_rule(
        prefix + "/deposit/<{}:pid_value>".format(_PID),
        endpoint="deposit-status",
        view_func=DepositStatusView.as_view(
            "service",
            serializers={"application/ld+json": serializers.jsonld_serializer,},
        ),
    )
    blueprint.add_url_rule(
        prefix + "/deposit/<{}:pid_value>/metadata".format(_PID),
        endpoint="deposit-metadata",
        view_func=DepositMetadataView.as_view(
            "service",
            serializers={"application/ld+json": serializers.jsonld_serializer,},
        ),
    )
    blueprint.add_url_rule(
        prefix + "/deposit/<{}:pid_value>/fileset".format(_PID),
        endpoint="deposit-fileset",
        view_func=DepositFilesetView.as_view(
            "service",
            serializers={"application/ld+json": serializers.jsonld_serializer,},
        ),
    )
    return blueprint


def create_wellknown_blueprint():
    """Provides /.well-known/sword-v3"""
    blueprint = Blueprint(
        "invenio_sword_wellknown", __name__, url_prefix="/.well-known"
    )

    def wellknown_response():
        return redirect("/api/sword/service-document")

    blueprint.add_url_rule(
        "sword-v3", endpoint="well-known", view_func=wellknown_response,
    )

    return blueprint
