import json

from flask import Response, request

sword_jsonld_context = "https://swordapp.github.io/swordv3/swordv3.jsonld"


def jsonld_serializer(data):
    data = {
        '@context': sword_jsonld_context,
        '@id': data.get('@id') or request.url,
        **data,
    }
    return Response(json.dumps(data, indent=2) + '\n', mimetype='application/ld+json')
