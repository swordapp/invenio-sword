import typing
from copy import deepcopy
from functools import partial
from http import HTTPStatus

from flask import Blueprint
from flask import current_app
from flask import redirect
from flask import request
from flask import Response
from flask import url_for
from invenio_db import db
from invenio_deposit.search import DepositSearch
from invenio_deposit.views.rest import create_error_handlers
from invenio_records_files.views import RecordObjectResource
from invenio_records_rest.utils import obj_or_import_string
from invenio_records_rest.views import need_record_permission
from invenio_records_rest.views import pass_record
from invenio_records_rest.views import verify_record_permission
from invenio_rest import ContentNegotiatedMethodView
from werkzeug.exceptions import Conflict
from werkzeug.exceptions import NotImplemented
from werkzeug.http import parse_options_header
from werkzeug.utils import cached_property

from . import serializers
from .api import SWORDDeposit
from .metadata import Metadata
from .packaging import IngestResult
from .typing import BytesReader


class SWORDDepositView(ContentNegotiatedMethodView):
    view_name: str
    record_class: typing.Type[SWORDDeposit]
    pid_type: str

    def __init__(self, serializers, ctx, *args, **kwargs):
        """Constructor."""
        super(SWORDDepositView, self).__init__(
            serializers,
            default_media_type=ctx.get("default_media_type"),
            *args,
            **kwargs,
        )
        for key, value in ctx.items():
            setattr(self, key, value)

    @cached_property
    def endpoint_options(self) -> typing.Dict[str, typing.Any]:
        return current_app.config["SWORD_ENDPOINTS"][self.pid_type]

    @cached_property
    def metadata_format(self):
        return request.headers.get(
            "Metadata-Format", self.endpoint_options["default_metadata_format"]
        )

    @cached_property
    def metadata_class(self):
        try:
            return self.endpoint_options["metadata_formats"][self.metadata_format]
        except KeyError as e:
            raise NotImplemented(  # noqa: F901
                "Unsupported Metadata-Format header value"
            ) from e

    @cached_property
    def packaging_class(self):
        packaging = request.headers.get(
            "Packaging", current_app.config["SWORD_DEFAULT_PACKAGING_FORMAT"]
        )
        try:
            return current_app.config["SWORD_PACKAGING_FORMATS"][packaging]
        except KeyError as e:
            raise NotImplemented(  # noqa: F901
                "Unsupported Packaging header value"
            ) from e

    @cached_property
    def in_progress(self) -> typing.Optional[bool]:
        return request.headers.get("In-Progress") == "true"

    def update_deposit_status(self, record: SWORDDeposit):
        if self.in_progress:
            if record["_deposit"]["status"] == "published":
                raise Conflict(
                    "Deposit has status {}; cannot subsequently be made In-Progress".format(
                        record["_deposit"]["status"]
                    )
                )
        elif record["_deposit"]["status"] == "draft":
            record["_deposit"]["status"] = "published"

    def create_deposit(self) -> SWORDDeposit:
        return SWORDDeposit.create({"metadata": {}})

    def update_deposit(
        self, record: SWORDDeposit, replace: bool = True
    ) -> typing.Optional[typing.Union[Metadata, IngestResult]]:
        result: typing.Optional[typing.Union[Metadata, IngestResult]] = None

        content_disposition, content_disposition_options = parse_options_header(
            request.headers.get("Content-Disposition", "")
        )

        metadata_deposit = content_disposition_options.get("metadata") == "true"
        by_reference_deposit = content_disposition_options.get("by-reference") == "true"

        if metadata_deposit:
            if by_reference_deposit:  # pragma: nocover
                record.set_metadata(
                    request.json["metadata"], self.metadata_class, replace=replace,
                )
            else:
                result = record.set_metadata(
                    request.stream,
                    self.metadata_class,
                    request.content_type,
                    replace=replace,
                )
        elif replace:
            record.set_metadata(None, self.metadata_class, replace=replace)

        if by_reference_deposit:  # pragma: nocover
            # This is the werkzeug HTTP exception, not the stdlib singleton, but flake8 can't work that out.
            raise NotImplemented  # noqa: F901

        if not (metadata_deposit or by_reference_deposit) and (
            request.content_type or request.content_length
        ):
            result = self.set_fileset_from_stream(
                record, request.stream, replace=replace
            )
        elif replace:
            self.set_fileset_from_stream(record, None, replace=replace)

        self.update_deposit_status(record)

        record.commit()
        db.session.commit()

        return result

    def set_fileset_from_stream(
        self, record: SWORDDeposit, stream: typing.Optional[BytesReader], replace=True
    ) -> IngestResult:
        return record.set_fileset_from_stream(
            stream if (request.content_type or request.content_length) else None,
            packaging_class=self.packaging_class,
            content_disposition=request.headers.get("Content-Disposition"),
            content_type=request.content_type,
            replace=replace,
        )


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
            "acceptPackaging": sorted(self.endpoint_options["packaging_formats"]),
            "acceptMetadata": sorted(self.endpoint_options["metadata_formats"]),
        }

    @need_record_permission("create_permission_factory")
    def post(self, **kwargs):
        record = self.create_deposit()

        # Check permissions
        permission_factory = self.create_permission_factory
        if permission_factory:
            verify_record_permission(permission_factory, record)

        self.update_deposit(record)

        response = self.make_response(record.get_status_as_jsonld())  # type: Response
        response.status_code = HTTPStatus.CREATED
        response.headers["Location"] = record.sword_status_url
        return response


class DepositStatusView(SWORDDepositView):
    view_name = "{}_item"

    @pass_record
    @need_record_permission("read_permission_factory")
    def get(self, pid, record: SWORDDeposit):
        return record.get_status_as_jsonld()

    @pass_record
    @need_record_permission("update_permission_factory")
    def post(self, pid, record: SWORDDeposit):
        result = self.update_deposit(record, replace=False)

        if isinstance(result, IngestResult) and result.original_deposit:
            response = Response(status=HTTPStatus.CREATED)
            response.headers["Location"] = url_for(
                "invenio_sword.{}_file".format(pid.pid_type),
                pid_value=pid.pid_value,
                key=result.original_deposit.key,
                _external=True,
            )
        elif isinstance(result, Metadata):
            response = Response(status=HTTPStatus.CREATED)
            response.headers["Location"] = record.sword_metadata_url
        else:
            response = Response(status=HTTPStatus.NO_CONTENT)

        return response

    @pass_record
    @need_record_permission("update_permission_factory")
    def put(self, pid, record: SWORDDeposit):
        self.update_deposit(record)
        return record.get_status_as_jsonld()

    @pass_record
    @need_record_permission("update_permission_factory")
    def delete(self, pid, record: SWORDDeposit):
        record.delete()
        record.commit()
        db.session.commit()
        return record.get_status_as_jsonld()


class DepositMetadataView(SWORDDepositView):
    view_name = "{}_metadata"

    @pass_record
    @need_record_permission("read_permission_factory")
    def get(self, pid, record: SWORDDeposit):
        return {
            "@id": record.sword_status_url,
            **record.get("swordMetadata", {}),
        }

    @pass_record
    @need_record_permission("update_permission_factory")
    def post(self, pid, record: SWORDDeposit):
        record.set_metadata(
            request.stream, self.metadata_class, request.content_type, replace=False
        )
        record.commit()
        db.session.commit()
        return Response(status=HTTPStatus.NO_CONTENT)

    @pass_record
    @need_record_permission("update_permission_factory")
    def put(self, pid, record: SWORDDeposit):
        record.set_metadata(request.stream, self.metadata_class, request.content_type)
        record.commit()
        db.session.commit()
        return Response(status=HTTPStatus.NO_CONTENT)

    @pass_record
    @need_record_permission("delete_permission_factory")
    def delete(self, pid, record: SWORDDeposit):
        record.set_metadata(None, self.metadata_class)
        record.commit()
        db.session.commit()
        return Response(status=HTTPStatus.NO_CONTENT)


class DepositFilesetView(SWORDDepositView):
    view_name = "{}_fileset"

    @pass_record
    @need_record_permission("update_permission_factory")
    def post(self, pid, record: SWORDDeposit):
        self.set_fileset_from_stream(
            record,
            request.stream
            if (request.content_type or request.content_length)
            else None,
            replace=False,
        )
        record.commit()
        db.session.commit()
        return Response(status=HTTPStatus.NO_CONTENT)

    @pass_record
    @need_record_permission("update_permission_factory")
    def put(self, pid, record: SWORDDeposit):
        self.set_fileset_from_stream(
            record,
            request.stream
            if (request.content_type or request.content_length)
            else None,
        )
        record.commit()
        db.session.commit()
        return Response(status=HTTPStatus.NO_CONTENT)

    @pass_record
    @need_record_permission("update_permission_factory")
    def delete(self, pid, record: SWORDDeposit):
        self.set_fileset_from_stream(
            record, None,
        )
        record.commit()
        db.session.commit()
        return Response(status=HTTPStatus.NO_CONTENT)


class DepositFileView(RecordObjectResource):
    view_name = "{}_file"


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
            pid_type=endpoint,
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
            options["item_route"],
            endpoint=DepositStatusView.view_name.format(endpoint),
            view_func=DepositStatusView.as_view(
                "item",
                serializers={"application/ld+json": serializers.jsonld_serializer,},
                ctx=ctx,
            ),
        )
        blueprint.add_url_rule(
            options["metadata_route"],
            endpoint=DepositMetadataView.view_name.format(endpoint),
            view_func=DepositMetadataView.as_view(
                "metadata",
                serializers={"application/ld+json": serializers.jsonld_serializer,},
                ctx=ctx,
            ),
        )
        blueprint.add_url_rule(
            options["fileset_route"],
            endpoint=DepositFilesetView.view_name.format(endpoint),
            view_func=DepositFilesetView.as_view(
                "fileset",
                serializers={"application/ld+json": serializers.jsonld_serializer,},
                ctx=ctx,
            ),
        )
        blueprint.add_url_rule(
            options["file_route"],
            endpoint=DepositFileView.view_name.format(endpoint),
            view_func=DepositFileView.as_view(
                name="file",
                serializers={
                    "*/*": lambda *args, **kwargs: Response(
                        status=HTTPStatus.NO_CONTENT
                    )
                },
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
