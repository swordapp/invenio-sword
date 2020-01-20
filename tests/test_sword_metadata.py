import pytest
from werkzeug.exceptions import UnsupportedMediaType

from invenio_sword.api import SWORDDeposit
from invenio_sword.metadata import SWORDMetadata


def test_parse_document(metadata_document):
    sword_metadata = SWORDMetadata.from_document(
        metadata_document, content_type="application/ld+json"
    )
    assert "@id" not in sword_metadata.data
    assert sword_metadata.data == {
        "@context": "https://swordapp.github.io/swordv3/swordv3.jsonld",
        "@type": "Metadata",
        "dc:title": "The title",
        "dcterms:abstract": "This is my abstract",
        "dc:contributor": "A.N. Other",
    }


def test_parse_document_with_wrong_content_type(metadata_document):
    with pytest.raises(UnsupportedMediaType):
        SWORDMetadata.from_document(metadata_document, content_type="text/yaml")


def test_update_record(metadata_document):
    sword_metadata = SWORDMetadata.from_document(
        metadata_document, content_type="application/ld+json"
    )
    record = SWORDDeposit(data={"metadata": {}})
    sword_metadata.update_record_metadata(record)
    assert record["metadata"]["title_statement"]["title"] == "The title"


def test_metadata_to_json(metadata_document):
    sword_metadata = SWORDMetadata.from_document(
        metadata_document, content_type="application/ld+json"
    )
    data = sword_metadata.to_json()
    assert data == sword_metadata.data
