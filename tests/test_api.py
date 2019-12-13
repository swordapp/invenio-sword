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
"""Test the API."""
import http.client
import re

from invenio_sword.api import pid_resolver


def test_get_service_document(api):
    with api.test_client() as client:
        response = client.get("/sword/service-document")
        assert response.status_code == 200
        assert response.is_json


def test_metadata_deposit_empty(api, location):
    with api.test_client() as client:
        response = client.post("/sword/service-document")
        assert response.status_code == http.client.CREATED
        match = re.match(
            "^http://localhost/sword/deposit/([^/]+)$", response.headers["Location"]
        )
        assert match is not None
        pid_value = match.group(1)
        _, record = pid_resolver.resolve(pid_value)
        assert dict(record) == {
            "metadata": {},
            "swordMetadata": {},
            "$schema": "http://localhost/schemas/deposits/deposit-v1.0.0.json",
            "_deposit": {"id": pid_value, "status": "published", "owners": []},
            "_bucket": record.bucket_id,
        }
