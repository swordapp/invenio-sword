from http import HTTPStatus

from flask import request, current_app
from flask import Response
from invenio_db import db
from werkzeug.http import parse_options_header

from invenio_records_rest.views import need_record_permission
from invenio_records_rest.views import pass_record
from invenio_rest import ContentNegotiatedMethodView

from . import SWORDDepositMixin
from ..api import SWORDDeposit

__all__ = ["DepositFilesetView"]

from ..schemas import ByReferenceSchema


class DepositFilesetView(SWORDDepositMixin, ContentNegotiatedMethodView):
    view_name = "{}_fileset"

    def update_fileset(self, record: SWORDDeposit, replace: bool):
        content_disposition, content_disposition_options = parse_options_header(
            request.headers.get("Content-Disposition", "")
        )
        by_reference_deposit = content_disposition_options.get("by-reference") == "true"

        if by_reference_deposit:
            by_reference_schema = ByReferenceSchema(
                context={"url_adapter": current_app.create_url_adapter(request)},
            )
            by_reference = by_reference_schema.load(request.json)
            record.set_by_reference_files(
                by_reference["files"],
                dereference_policy=self.endpoint_options["dereference_policy"],
                request_url=request.url,
                replace=replace,
            )
        else:
            self.ingest_file(
                record,
                request.stream
                if (request.content_type or request.content_length)
                else None,
                replace=replace,
            )
        record.commit()
        db.session.commit()

    @pass_record
    @need_record_permission("update_permission_factory")
    def post(self, pid, record: SWORDDeposit):
        self.update_fileset(record, replace=False)
        return Response(status=HTTPStatus.NO_CONTENT)

    @pass_record
    @need_record_permission("update_permission_factory")
    def put(self, pid, record: SWORDDeposit):
        self.update_fileset(record, replace=True)
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
