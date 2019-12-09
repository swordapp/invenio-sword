import json

from flask import request
from flask import Response

sword_jsonld_context = "https://swordapp.github.io/swordv3/swordv3.jsonld"


def jsonld_serializer(data, **kwargs):
    kwargs.setdefault("mimetype", "application/ld+json")
    data = {
        "@context": sword_jsonld_context,
        "@id": data.get("@id") or request.url,
        **data,
    }
    return Response(json.dumps(data, indent=2) + "\n", **kwargs)
