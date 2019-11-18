from flask import current_app, request
from invenio_rest import ContentNegotiatedMethodView


class ServiceDocumentView(ContentNegotiatedMethodView):
    def get(self):
        return {
            '@type': 'ServiceDocument',
            'dc:title': current_app.config['THEME_SITENAME'],
            'root': request.url,
            'acceptDeposits': True,
            'version': 'http://purl.org/net/sword/3.0',
            'maxUploadSize': current_app.config['SWORD_MAX_UPLOAD_SIZE'],
            'maxByReferenceSize': current_app.config['SWORD_MAX_BY_REFERENCE_SIZE'],
            'acceptPackaging': sorted(current_app.config['SWORD_PACKAGING_FORMATS']),
        }

    def post(self):
        pass
