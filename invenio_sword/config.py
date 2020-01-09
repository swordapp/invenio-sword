import pkg_resources
from invenio_deposit.config import DEPOSIT_REST_ENDPOINTS

SWORD_MAX_UPLOAD_SIZE = 1024 ** 3  # 1 GiB
SWORD_MAX_BY_REFERENCE_SIZE = 10 * 1024 ** 3  # 10 GiB

_PID = 'pid(depid,record_class="invenio_sword.api:SWORDDeposit")'

SWORD_ENDPOINTS = {
    name: {
        **options,
        "packaging_formats": {
            ep.name: ep.load()
            for ep in pkg_resources.iter_entry_points("invenio_sword.packaging")
        },
        "metadata_formats": {
            ep.name: ep.load()
            for ep in pkg_resources.iter_entry_points("invenio_sword.metadata")
        },
        "default_packaging_format": "http://purl.org/net/sword/3.0/package/Binary",
        "default_metadata_format": "http://purl.org/net/sword/3.0/types/Metadata",
        "record_class": "invenio_sword.api:Deposit",
        "default_media_type": "application/ld+json",
        "service_document_route": "/sword/service-document",
        "deposit_status_route": "/sword/deposit/<{}:pid_value>".format(_PID),
        "deposit_metadata_route": "/sword/deposit/<{}:pid_value>/metadata".format(_PID),
        "deposit_fileset_route": "/sword/deposit/<{}:pid_value>/fileset".format(_PID),
    }
    for name, options in DEPOSIT_REST_ENDPOINTS.items()
}

SWORD_PACKAGING_FORMATS = {
    ep.name: ep.load()
    for ep in pkg_resources.iter_entry_points("invenio_sword.packaging")
}

SWORD_DEFAULT_PACKAGING_FORMAT = "http://purl.org/net/sword/3.0/package/Binary"

SWORD_DEFAULT_METADATA_FORMAT = "http://purl.org/net/sword/3.0/types/Metadata"
