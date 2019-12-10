import pkg_resources

SWORD_MAX_UPLOAD_SIZE = 1024 ** 3  # 1 GiB
SWORD_MAX_BY_REFERENCE_SIZE = 10 * 1024 ** 3  # 10 GiB

SWORD_PACKAGING_FORMATS = {
    ep.name: ep.load()
    for ep in pkg_resources.iter_entry_points("invenio_sword.packaging")
}


SWORD_METADATA_FORMATS = {
    ep.name: ep.load()
    for ep in pkg_resources.iter_entry_points("invenio_sword.metadata")
}

SWORD_DEFAULT_PACKAGING_FORMAT = "http://purl.org/net/sword/3.0/package/Binary"

SWORD_DEFAULT_METADATA_FORMAT = "http://purl.org/net/sword/3.0/types/Metadata"
