import math
from flask import current_app

from marshmallow import fields, validates, validates_schema, ValidationError
from marshmallow import Schema
from marshmallow import validate

__all__ = ["ByReferenceSchema"]

from marshmallow.validate import Range

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


class SegmentInitSchema(Schema):
    """For validating parameters on `Content-Disposition: segment-init` headers"""

    # validate parameters are lambdas to defer accessing current_app until we're inside the application context

    size = fields.Integer(
        required=True,
        validate=lambda value: Range(
            current_app.config["FILES_REST_MULTIPART_MAX_PARTS"]
        ),
    )
    segment_count = fields.Integer(
        required=True,
        validate=lambda value: Range(
            1, current_app.config["FILES_REST_MULTIPART_MAX_PARTS"]
        ),
    )
    segment_size = fields.Integer(
        required=True,
        validate=lambda value: Range(
            current_app.config["FILES_REST_MULTIPART_CHUNKSIZE_MIN"],
            current_app.config["FILES_REST_MULTIPART_CHUNKSIZE_MAX"],
        )(value),
    )

    @validates_schema
    def validate_segment_count(self, data, **kwargs):
        if data["segment_count"] != math.ceil(data["size"] / data["segment_size"]):
            raise ValidationError(
                {
                    "segment_count": "Wrong number of segments for given size and segment_size."
                }
            )


class SegmentUploadSchema(Schema):
    segment_number = fields.Integer(required=True)

    def __init__(self, *args, segment_count, **kwargs):
        self._segment_count = segment_count
        super().__init__(*args, **kwargs)

    @validates("segment_number")
    def validate_segment_number(self, value):
        return Range(1, self._segment_count)(value)
