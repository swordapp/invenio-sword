# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016 CERN.
#
# Invenio is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.
"""Test the BagIt implementation."""
import os
from http import HTTPStatus

from flask import url_for
from flask_security import url_for_security
from invenio_files_rest.models import Bucket
from invenio_files_rest.models import ObjectVersion

fixtures_path = os.path.join(os.path.dirname(__file__), "fixtures")


def test_post_service_document_with_simple_zip(api, users, location):
    with api.test_request_context(), api.test_client() as client:
        client.post(
            url_for_security("login"),
            data={"email": users[0]["email"], "password": "tester"},
        )

        with open(os.path.join(fixtures_path, "simple.zip"), "rb") as f:
            response = client.post(
                url_for("invenio_sword.depid_service_document"),
                input_stream=f,
                headers={
                    "Content-Type": "application/zip",
                    "Packaging": "http://purl.org/net/sword/3.0/package/SimpleZip",
                },
            )

        assert response.status_code == HTTPStatus.CREATED

        bucket = Bucket.query.one()
        obj_1 = ObjectVersion.query.filter_by(bucket=bucket, key="example.svg").one()
        obj_2 = ObjectVersion.query.filter_by(bucket=bucket, key="hello.txt").one()

        assert obj_1.mimetype == "image/svg+xml"
        assert obj_2.mimetype == "text/plain"
