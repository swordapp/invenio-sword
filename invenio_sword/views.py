import http.client
from copy import deepcopy
from functools import partial

from flask import Blueprint
from flask import current_app
from flask import redirect
from flask import request
from flask import Response
from invenio_db import db
from invenio_deposit.search import DepositSearch
from invenio_deposit.views.rest import create_error_handlers
from invenio_records_rest.utils import obj_or_import_string
from invenio_records_rest.views import need_record_permission
from invenio_records_rest.views import pass_record
from invenio_records_rest.views import verify_record_permission
from invenio_rest import ContentNegotiatedMethodView
from werkzeug.exceptions import BadRequest
from werkzeug.exceptions import NotFound
from werkzeug.exceptions import NotImplemented
from werkzeug.http import parse_options_header

from . import serializers
from .api import SWORDDeposit
from invenio_sword.metadata import JSONMetadata
from invenio_sword.metadata import Metadata


class SWORDDepositView(ContentNegotiatedMethodView):
    view_name: str
    record_class: type

    def __init__(self, serializers, ctx, *args, **kwargs):
        """Constructor."""
        super(SWORDDepositView, self).__init__(
            serializers,
            default_media_type=ctx.get("default_media_type"),
            *args,
            **kwargs
        )
        for key, value in ctx.items():
            setattr(self, key, value)


class ServiceDocumentView(SWORDDepositView):
    view_name = "{}_service_document"

    def get(self):
        return {
            "@type": "ServiceDocument",
            "dc:title": current_app.config["THEME_SITENAME"],
            "root": request.url,
            "acceptDeposits": True,
            "version": "http://purl.org/net/sword/3.0",
            "maxUploadSize": current_app.config["SWORD_MAX_UPLOAD_SIZE"],
            "maxByReferenceSize": current_app.config["SWORD_MAX_BY_REFERENCE_SIZE"],
            "acceptArchiveFormat": ["application/zip"],
            "acceptPackaging": sorted(current_app.config["SWORD_PACKAGING_FORMATS"]),
            "acceptMetadata": sorted(current_app.config["SWORD_METADATA_FORMATS"]),
        }

    @need_record_permission("create_permission_factory")
    def post(self, **kwargs):
        content_disposition, content_disposition_options = parse_options_header(
            request.headers.get("Content-Disposition", "")
        )
        content_type, _ = parse_options_header(request.content_type)
        filename = content_disposition_options.get("filename")
        in_progress = request.headers.get("In-Progress") == "true"
        packaging = request.headers.get(
            "Packaging", current_app.config["SWORD_DEFAULT_PACKAGING_FORMAT"]
        )
        metadata_format = request.headers.get(
            "Metadata-Format", current_app.config["SWORD_DEFAULT_METADATA_FORMAT"]
        )

        try:
            packaging = current_app.config["SWORD_PACKAGING_FORMATS"][packaging]()
        except KeyError:
            raise BadRequest("Unexpected packaging format")

        # print(request.files)
        record = SWORDDeposit.create({"metadata": {}, "swordMetadata": {},})
        record["_deposit"]["status"] = "draft" if in_progress else "published"

        # Check permissions
        permission_factory = self.create_permission_factory
        if permission_factory:
            verify_record_permission(permission_factory, record)

        metadata_deposit = content_disposition_options.get("metadata") == "true"
        by_reference_deposit = content_disposition_options.get("by-reference") == "true"

        if metadata_deposit:
            metadata_cls: Metadata = current_app.config["SWORD_METADATA_FORMATS"][
                metadata_format
            ]
            if by_reference_deposit:
                if not isinstance(metadata_cls, JSONMetadata):
                    raise BadRequest(
                        "Metadata-Format must be JSON-based to use Metadata+By-Reference deposit"
                    )
                record.sword_metadata = metadata_cls.from_document(
                    request.json["metadata"], content_type=metadata_cls.content_type
                )
            else:
                record.sword_metadata = metadata_cls.from_document(
                    request.stream,
                    content_type=request.content_type,
                    encoding=request.content_encoding,
                )

        if by_reference_deposit:
            # This is the werkzeug HTTP exception, not the stdlib singleton, but flake8 can't work that out.
            raise NotImplemented  # noqa: F901

        if not (metadata_deposit or by_reference_deposit):
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
        response.headers["Location"] = record.sword_status_url
        return response


class DepositStatusView(SWORDDepositView):
    view_name = "{}_deposit_status"

    @pass_record
    @need_record_permission("read_permission_factory")
    def get(self, pid, record: SWORDDeposit):
        return record.get_status_as_jsonld()


class DepositMetadataView(SWORDDepositView):
    view_name = "{}_deposit_metadata"

    @pass_record
    @need_record_permission("read_permission_factory")
    def get(self, pid, record: SWORDDeposit):
        sword_metadata = record.sword_metadata
        if not sword_metadata:
            raise NotFound
        response = Response(
            sword_metadata.to_document(request.url),
            content_type=sword_metadata.content_type,
        )
        response.headers["Metadata-Format"] = record.sword_metadata_format
        return response

    @pass_record
    @need_record_permission("update_permission_factory")
    def put(self, pid, record: SWORDDeposit):
        metadata_format = request.headers.get("Metadata-Format")
        if not metadata_format:
            raise BadRequest("Missing Metadata-Format header")
        try:
            metadata_cls = current_app.config["SWORD_METADATA_FORMATS"][metadata_format]
        except KeyError:
            raise NotImplemented  # noqa: F901
        record.sword_metadata = metadata_cls.from_document(
            request.stream, content_type=request.content_type
        )
        record.commit()
        db.session.commit()
        return Response(status=http.client.NO_CONTENT)

    @pass_record
    @need_record_permission("delete_permission_factory")
    def delete(self, pid, record: SWORDDeposit):
        record.sword_metadata = None
        record.commit()
        db.session.commit()
        return Response(status=http.client.NO_CONTENT)


class DepositFilesetView(SWORDDepositView):
    view_name = "{}_deposit_fileset"

    @pass_record
    @need_record_permission("read_permission_factory")
    def get(self, pid, record: SWORDDeposit):
        raise NotImplementedError  # pragma: nocover


def create_blueprint(endpoints):
    """Create Invenio-SWORD blueprint.

    See: :data:`invenio_sword.config.SWORD_ENDPOINTS`.

    :param endpoints: List of endpoints configuration.
    :returns: The configured blueprint.
    """
    blueprint = Blueprint("invenio_sword", __name__, url_prefix="",)
    create_error_handlers(blueprint)

    for endpoint, options in (endpoints or {}).items():
        options = deepcopy(options)

        options.setdefault("search_class", DepositSearch)
        search_class = obj_or_import_string(options["search_class"])

        # records rest endpoints will use the deposit class as record class
        options.setdefault("record_class", SWORDDeposit)
        record_class = obj_or_import_string(options["record_class"])

        # backward compatibility for indexer class
        options.setdefault("indexer_class", None)

        search_class_kwargs = {}
        if options.get("search_index"):
            search_class_kwargs["index"] = options["search_index"]

        if options.get("search_type"):
            search_class_kwargs["doc_type"] = options["search_type"]

        ctx = dict(
            read_permission_factory=obj_or_import_string(
                options.get("read_permission_factory_imp")
            ),
            create_permission_factory=obj_or_import_string(
                options.get("create_permission_factory_imp")
            ),
            update_permission_factory=obj_or_import_string(
                options.get("update_permission_factory_imp")
            ),
            delete_permission_factory=obj_or_import_string(
                options.get("delete_permission_factory_imp")
            ),
            record_class=record_class,
            search_class=partial(search_class, **search_class_kwargs),
            default_media_type=options.get("default_media_type"),
        )

        blueprint.add_url_rule(
            options["service_document_route"],
            endpoint=ServiceDocumentView.view_name.format(endpoint),
            view_func=ServiceDocumentView.as_view(
                "service",
                serializers={"application/ld+json": serializers.jsonld_serializer,},
                ctx=ctx,
            ),
        )

        blueprint.add_url_rule(
            options["deposit_status_route"],
            endpoint=DepositStatusView.view_name.format(endpoint),
            view_func=DepositStatusView.as_view(
                "service",
                serializers={"application/ld+json": serializers.jsonld_serializer,},
                ctx=ctx,
            ),
        )
        blueprint.add_url_rule(
            options["deposit_metadata_route"],
            endpoint=DepositMetadataView.view_name.format(endpoint),
            view_func=DepositMetadataView.as_view(
                "service",
                serializers={"application/ld+json": serializers.jsonld_serializer,},
                ctx=ctx,
            ),
        )
        blueprint.add_url_rule(
            options["deposit_fileset_route"],
            endpoint=DepositFilesetView.view_name.format(endpoint),
            view_func=DepositFilesetView.as_view(
                "service",
                serializers={"application/ld+json": serializers.jsonld_serializer,},
                ctx=ctx,
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
