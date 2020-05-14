from flask import request, current_app
from invenio_db import db
from werkzeug.http import parse_options_header

import sword3common.exceptions
from invenio_records_files.views import RecordObjectResource, pass_bucket_id

__all__ = ["DepositFileView"]

from invenio_records_rest.views import pass_record
from invenio_sword.schemas import ByReferenceSchema
from invenio_sword.views import SWORDDepositMixin
from sword3common.constants import PackagingFormat


class DepositFileView(SWORDDepositMixin, RecordObjectResource):
    view_name = "{}_file"

    @pass_record
    @pass_bucket_id
    def put(self, pid, record, **kwargs):
        content_disposition, content_disposition_options = parse_options_header(
            request.headers.get("Content-Disposition", "")
        )
        by_reference_deposit = content_disposition_options.get("by-reference") == "true"

        if by_reference_deposit:
            by_reference_schema = ByReferenceSchema(
                context={
                    "url_adapter": current_app.create_url_adapter(request),
                    "binary_packaging_only": True,
                    "max_files": 1,
                },
            )
            by_reference = by_reference_schema.load(request.json)
            # if len(by_reference["files"]) != 1:
            #     raise sword3common.exceptions.ValidationFailed(
            #         "Must be exactly one by-reference file when replacing a single file"
            #     )
            record.set_by_reference_files(
                by_reference["files"],
                dereference_policy=self.endpoint_options["dereference_policy"],
                request_url=request.url,
                replace=False,
            )
            record.commit()
            db.session.commit()
        else:
            return super().put(pid_value=pid.pid_value, **kwargs)
