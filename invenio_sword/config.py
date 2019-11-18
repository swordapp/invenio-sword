SWORD_MAX_UPLOAD_SIZE = 1024 ** 3  # 1 GiB
SWORD_MAX_BY_REFERENCE_SIZE = 10 * 1024 ** 3  # 10 GiB

SWORD_PACKAGING_FORMATS = {
    'http://purl.org/net/sword/3.0/package/Binary': 'invenio_sword.packaging:BinaryPackaging',
    'http://purl.org/net/sword/3.0/package/SimpleZip': 'invenio_sword.packaging:SimpleZipPackaging',
    'http://purl.org/net/sword/3.0/package/SWORDBagIt': 'invenio_sword.packaging:SWORDBagItPackaging',
}