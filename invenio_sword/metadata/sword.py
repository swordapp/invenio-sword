from __future__ import annotations

import json
import typing
import uuid

import rdflib
from rdflib.namespace import DC
from werkzeug.exceptions import BadRequest
from werkzeug.exceptions import UnsupportedMediaType

from .base import JSONMetadata
from invenio_sword.api import SWORDDeposit
from invenio_sword.typing import BytesReader

__all__ = ["SWORDMetadata"]


class SWORDMetadata(JSONMetadata):
    content_type = "application/ld+json"

    def __init__(self, data):
        self.data = data

    @classmethod
    def from_document(
        cls,
        document: typing.Union[BytesReader, dict],
        content_type: str,
        encoding: str = "utf_8",
    ) -> SWORDMetadata:
        if content_type not in (cls.content_type, "application/json"):
            raise UnsupportedMediaType(
                "Content-Type must be {}".format(cls.content_type)
            )
        if isinstance(document, BytesReader):
            try:
                data = json.load(document, encoding=encoding)
            except json.JSONDecodeError as e:
                raise BadRequest("Unable to parse JSON") from e
        else:
            data = document
        data.pop("@id", None)
        return cls(data)

    def update_record_metadata(
        self, record: SWORDDeposit,
    ):
        graph = rdflib.Graph()
        subject = rdflib.URIRef("urn:uuid:" + str(uuid.uuid4()))

        data = {
            **self.data,
            "@id": str(subject),
        }
        graph.parse(data=json.dumps(data), format="json-ld")

        predicates = set(graph.predicates(subject=subject))

        if "metadata" not in record:
            record["metadata"] = {}

        if DC.title in predicates:
            if "title_statement" not in record["metadata"]:
                record["metadata"]["title_statement"] = {}
            record["metadata"]["title_statement"]["title"] = str(
                graph.value(subject, DC.title)
            )
        elif "title" in record["metadata"].get("title_statement", {}):
            del record["metadata"]["title_statement"]["title"]

    def to_json(self):
        # Record the full SWORD metadata without the '@id' key
        return {k: self.data[k] for k in self.data if k != "@id"}

    def to_document(self, metadata_url):
        return json.dumps({**self.data, "@id": metadata_url}, indent=2)

    def __add__(self, other):
        if not isinstance(other, SWORDMetadata):
            return NotImplemented
        return type(self)({**self.data, **other.data})
