import datetime
import json
import typing
from copy import deepcopy
from functools import partial
from http import HTTPStatus

import marshmallow
import sword3common.constants
import sword3common.exceptions
from flask import Blueprint
from flask import current_app
from flask import request
from flask import Response
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
from werkzeug.http import parse_options_header
from werkzeug.utils import cached_property

from . import serializers
from .api import SWORDDeposit
from .metadata import Metadata
from .schemas import ByReferenceSchema
from .typing import BytesReader
from .typing import SwordEndpointDefinition


class SWORDDepositView(ContentNegotiatedMethodView):
    """
    Base class for all SWORD views

    The properties and methods defined on this class are used by subclasses to SWORD operations with common
    implementations across different SWORD views.
    """

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

    def dispatch_request(self, *args, **kwargs):
        try:
            return super().dispatch_request(*args, **kwargs)
        except sword3common.exceptions.SwordException as e:
            return Response(
                json.dumps(
                    {
                        "@context": sword3common.constants.JSON_LD_CONTEXT,
                        "@type": e.name,
                        "error": e.reason,
                        "log": e.message,
                        "timestamp": e.timestamp.isoformat(),
                    }
                ),
                content_type="application/ld+json",
                status=e.status_code,
            )
        except marshmallow.exceptions.ValidationError as e:
            return Response(
                json.dumps(
                    {
                        "@context": sword3common.constants.JSON_LD_CONTEXT,
                        "@type": sword3common.exceptions.ValidationFailed.name,
                        "error": sword3common.exceptions.ValidationFailed.reason,
                        "timestamp": datetime.datetime.now(
                            tz=datetime.timezone.utc
                        ).isoformat(),
                        "errors": e.messages,
                    }
                ),
                content_type="application/ld+json",
                status=sword3common.exceptions.ValidationFailed.status_code,
            )

    @cached_property
    def endpoint_options(self) -> typing.Dict[str, typing.Any]:
        """Configuration endpoints for this view's SWORD endpoint"""
        return current_app.config["SWORD_ENDPOINTS"][self.pid_type]

    @cached_property
    def metadata_format(self) -> str:
        """The ``Metadata-Format`` header, or its default per config"""
        return request.headers.get(
            "Metadata-Format", self.endpoint_options["default_metadata_format"]
        )

    @cached_property
    def metadata_class(self) -> typing.Type[Metadata]:
        """The Metadata subclass associated with the request.

        :raises NotImplemented: if the ``Metadata-Format`` is not supported
        """
        try:
            return self.endpoint_options["metadata_formats"][self.metadata_format]
        except KeyError as e:
            raise sword3common.exceptions.MetadataFormatNotAcceptable from e

    @cached_property
    def packaging_name(self) -> str:
        """The Packaging subclass associated with the request.

        :raises NotImplemented: if the ``Packaging`` is not supported
        """
        packaging = request.headers.get(
            "Packaging", self.endpoint_options["default_packaging_format"]
        )
        if packaging not in self.endpoint_options["packaging_formats"]:
            raise sword3common.exceptions.PackagingFormatNotAcceptable
        return packaging

    @cached_property
    def in_progress(self) -> bool:
        """Whether the request declares that the deposit is still in progress, via the ``In-Progress`` header"""
        return request.headers.get("In-Progress") == "true"

    def update_deposit_status(self, record: SWORDDeposit) -> None:
        """Updates a deposit status from the In-Progress header

        """
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
        """Create an empty deposit record"""
        return SWORDDeposit.create({"metadata": {}})

    def update_deposit(self, record: SWORDDeposit, replace: bool = True):
        """Update a deposit according to the request data

        :param replace: If ``True``, all previous data on the deposit is removed. If ``False``, the request augments
            data already provided.
        """

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
                record.set_metadata(
                    request.stream,
                    self.metadata_class,
                    request.content_type,
                    replace=replace,
                )
        elif replace:
            record.set_metadata(None, self.metadata_class, replace=replace)

        if by_reference_deposit:  # pragma: nocover
            if metadata_deposit:
                by_reference = ByReferenceSchema().load(request.json["by-reference"])
            else:
                by_reference = ByReferenceSchema().load(request.json)
            record.set_by_reference_files(
                by_reference["files"],
                dereference_policy=self.endpoint_options["dereference_policy"],
                replace=replace,
            )
        elif replace:
            record.set_by_reference_files(
                [],
                dereference_policy=self.endpoint_options["dereference_policy"],
                replace=replace,
            )

        if not (metadata_deposit or by_reference_deposit) and (
            request.content_type or request.content_length
        ):
            self.ingest_file(record, request.stream, replace=replace)
        elif replace:
            self.ingest_file(record, None, replace=replace)

        self.update_deposit_status(record)

        record.commit()
        db.session.commit()

    def ingest_file(
        self, record: SWORDDeposit, stream: typing.Optional[BytesReader], replace=True
    ):
        """
        Sets or adds to a deposit fileset using a bytestream and request headers

        This method wraps ``record.set_fileset_from_stream()`` with appropriate arguments.

        :param record: The SWORDDeposit record to modify
        :param stream: A bytestream of the file or package to be deposited
        :param replace: Whether to replace or add to the deposit
        :return: an IngestResult
        """
        return record.ingest_file(
            stream if (request.content_type or request.content_length) else None,
            packaging_name=self.packaging_name,
            content_disposition=request.headers.get("Content-Disposition"),
            content_type=request.content_type,
            replace=replace,
        )


class ServiceDocumentView(SWORDDepositView):
    view_name = "{}_service_document"

    def get(self):
        """Retrieve the service document

        :see also: https://swordapp.github.io/swordv3/swordv3.html#9.2.
        """
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
        """Initiate a SWORD deposit"""
        record = self.create_deposit()

        # Check permissions
        permission_factory = self.create_permission_factory
        if permission_factory:
            verify_record_permission(permission_factory, record)

        self.update_deposit(record, replace=False)

        response = self.make_response(record.get_status_as_jsonld())  # type: Response
        response.status_code = HTTPStatus.CREATED
        response.headers["Location"] = record.sword_status_url
        return response


class DepositStatusView(SWORDDepositView):
    view_name = "{}_item"

    @pass_record
    @need_record_permission("read_permission_factory")
    def get(self, pid, record: SWORDDeposit):
        """Retrieve a SWORD status document for a deposit record

        :see also: https://swordapp.github.io/swordv3/swordv3.html#9.6.
        """
        return record.get_status_as_jsonld()

    @pass_record
    @need_record_permission("update_permission_factory")
    def post(self, pid, record: SWORDDeposit):
        """Augment a SWORD deposit with either metadata or files"""
        self.update_deposit(record, replace=False)
        return record.get_status_as_jsonld()

    @pass_record
    @need_record_permission("update_permission_factory")
    def put(self, pid, record: SWORDDeposit):
        """Replace a SWORD deposit with either metadata or files"""
        self.update_deposit(record)
        return record.get_status_as_jsonld()

    @pass_record
    @need_record_permission("update_permission_factory")
    def delete(self, pid, record: SWORDDeposit):
        """Delete a SWORD deposit"""
        record.delete()
        db.session.commit()
        return Response(status=HTTPStatus.NO_CONTENT)


class DepositMetadataView(SWORDDepositView):
    view_name = "{}_metadata"

    @pass_record
    @need_record_permission("read_permission_factory")
    def get(self, pid, record: SWORDDeposit):
        """
        Retrieve the deposit's SWORD metadata as a JSON-LD document

        This will return the empty document with a 200 status if no metadata is available
        """
        return {
            "@id": record.sword_status_url,
            **record.get("swordMetadata", {}),
        }

    @pass_record
    @need_record_permission("update_permission_factory")
    def post(self, pid, record: SWORDDeposit):
        """
        Extend the metadata with new metadata from the request body

        :param pid: The persistent identifier for the deposit
        :param record: The SWORDDeposit object
        :raises Conflict: if there is existing metadata that doesn't support the ``+`` operation
        :return: a 204 No Content response
        """
        record.set_metadata(
            request.stream, self.metadata_class, request.content_type, replace=False
        )
        record.commit()
        db.session.commit()
        return Response(status=HTTPStatus.NO_CONTENT)

    @pass_record
    @need_record_permission("update_permission_factory")
    def put(self, pid, record: SWORDDeposit):
        """
        Set the metadata with new metadata from the request body

        :param pid: The persistent identifier for the deposit
        :param record: The SWORDDeposit object
        :return: a 204 No Content response
        """
        record.set_metadata(request.stream, self.metadata_class, request.content_type)
        record.commit()
        db.session.commit()
        return Response(status=HTTPStatus.NO_CONTENT)

    @pass_record
    @need_record_permission("delete_permission_factory")
    def delete(self, pid, record: SWORDDeposit):
        """
        Delete ny existing metadata of the format given by the Metadata-Format header

        :param pid: The persistent identifier for the deposit
        :param record: The SWORDDeposit object
        :return: a 204 No Content response
        """
        record.set_metadata(None, self.metadata_class)
        record.commit()
        db.session.commit()
        return Response(status=HTTPStatus.NO_CONTENT)


class DepositFilesetView(SWORDDepositView):
    view_name = "{}_fileset"

    @pass_record
    @need_record_permission("update_permission_factory")
    def post(self, pid, record: SWORDDeposit):
        self.ingest_file(
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
        self.ingest_file(
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
        self.ingest_file(
            record, None,
        )
        record.commit()
        db.session.commit()
        return Response(status=HTTPStatus.NO_CONTENT)


class DepositFileView(RecordObjectResource):
    view_name = "{}_file"


def create_blueprint(endpoints: typing.Dict[str, SwordEndpointDefinition]) -> Blueprint:
    """
    Create an Invenio-SWORD blueprint

    This takes a list of endpoint definitions and returns a SWORD blueprint for use in Invenio. You shouldn't need to
    use this directly, as it's called by :class:`invenio_sword.ext.InvenioSword`.

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
