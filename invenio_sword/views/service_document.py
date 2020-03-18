from http import HTTPStatus

from flask import current_app
from flask import request
from flask import Response
from invenio_records_rest.views import need_record_permission
from invenio_records_rest.views import verify_record_permission

from . import SWORDDepositView

__all__ = ["ServiceDocumentView"]


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
