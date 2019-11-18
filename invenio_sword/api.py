from flask import Blueprint, url_for, redirect

from . import serializers, views


def create_blueprint(prefix='/sword'):
    blueprint = Blueprint(
        'invenio_sword',
        __name__,
        url_prefix='',
    )

    blueprint.add_url_rule(
        prefix + '/service-document',
        endpoint='service-document',
        view_func=views.ServiceDocumentView.as_view(
            'service',
            serializers={
                'application/ld+json': serializers.jsonld_serializer,
            }
        ),
    )
    return blueprint
