import enum


class ObjectTagKey(enum.Enum):
    OriginalDeposit = "invenio_sword.originalDeposit"
    DerivedFrom = "invenio_sword.derivedFrom"
    FileSetFile = "invenio_sword.fileSetFile"
    Packaging = "invenio_sword.packaging"
    MetadataFormat = "invenio_sword.metadataFormat"
    ByReferenceURL = "invenio_sword.byReferenceURL"
    ByReferenceDereference = "invenio_sword.byReferenceDereference"
    ByReferenceTTL = "invenio_sword.byReferenceTTL"
    ByReferenceContentLength = "invenio_sword.byReferenceContentLength"
