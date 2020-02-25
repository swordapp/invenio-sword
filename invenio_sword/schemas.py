from marshmallow import fields
from marshmallow import Schema
from marshmallow import validate

__all__ = ["ByReferenceSchema"]

from sword3common.constants import PackagingFormat, JSON_LD_CONTEXT


class _ByReferenceFileSchema(Schema):
    uri = fields.Url(data_key="@id", required=True)
    content_disposition = fields.String(data_key="contentDisposition", required=True)
    content_length = fields.Integer(data_key="contentLength", strict=True)
    content_type = fields.String(data_key="contentType", required=True)
    dereference = fields.Boolean(required=True)
    packaging = fields.String(missing=PackagingFormat.Binary)
    ttl = fields.AwareDateTime()


class ByReferenceSchema(Schema):
    jsonld_context = fields.String(
        data_key="@context",
        validate=[validate.OneOf([JSON_LD_CONTEXT])],
        required=True,
    )
    jsonld_type = fields.String(
        data_key="@type", validate=[validate.OneOf(["ByReference"])], required=True,
    )
    files = fields.List(
        fields.Nested(_ByReferenceFileSchema),
        data_key="byReferenceFiles",
        required=True,
    )
