"""
Segmented file upload support

See <https://swordapp.github.io/swordv3/swordv3.html#9.7.>.
"""

from invenio_rest import ContentNegotiatedMethodView

__all__ = ["StagingURLView", "TemporaryURLView"]


class StagingURLView(ContentNegotiatedMethodView):
    """POST to this to start a segmented file upload and create a temporary URL"""

    view_name = "{}_staging_url"


class TemporaryURLView(ContentNegotiatedMethodView):
    """Upload file segments here"""

    view_name = "{}_temporary_url"
