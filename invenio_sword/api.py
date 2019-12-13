from __future__ import annotations

import functools
import logging
from typing import Optional
from typing import TYPE_CHECKING

from flask import current_app
from flask import url_for
from invenio_deposit.api import Deposit
from invenio_pidstore.resolver import Resolver

if TYPE_CHECKING:
    from .metadata import Metadata


logger = logging.getLogger(__name__)


class SWORDDeposit(Deposit):
    def get_status_as_jsonld(self):
        return {
            "@type": "Status",
            "metadata": {"@id": self.sword_metadata_url,},
            "fileSet": {"@id": self.sword_fileset_url,},
            "service": url_for("invenio_sword.service-document"),
            "state": self.sword_states,
        }

    @property
    def sword_states(self):
        states = []
        if self["_deposit"].get("status") == "draft":
            states.append(
                {
                    "@id": "http://purl.org/net/sword/3.0/state/inProgress",
                    "description": "the item is currently inProgress",
                }
            )
        return states

    @property
    def sword_status_url(self):
        return url_for("invenio_sword.deposit-status", pid_value=self.pid.pid_value)

    @property
    def sword_metadata_url(self):
        return url_for("invenio_sword.deposit-metadata", pid_value=self.pid.pid_value)

    @property
    def sword_fileset_url(self):
        return url_for("invenio_sword.deposit-fileset", pid_value=self.pid.pid_value)

    @property
    def sword_metadata_format(self):
        return self.get("swordMetadataFormat")

    @property
    def sword_metadata(self) -> Optional[Metadata]:
        if self.sword_metadata_format:
            try:
                metadata_cls = current_app.config["SWORD_METADATA_FORMATS"][
                    self.sword_metadata_format
                ]
            except KeyError:
                logger.warning(
                    "Metadata format for record %s (%s) not supported",
                    self.pid.pid_value,
                    self.sword_metadata_format,
                )
                return None
            return metadata_cls(self["swordMetadata"])
        else:
            return None

    @sword_metadata.setter
    def sword_metadata(self, metadata: Optional[Metadata]):
        if metadata is None:
            del self["swordMetadataFormat"]
            del self["swordMetadata"]
        else:
            for metadata_format, metadata_cls in current_app.config[
                "SWORD_METADATA_FORMATS"
            ].items():
                if isinstance(metadata, metadata_cls):
                    break
            else:
                raise ValueError(
                    "Metadata format %s is not configured", type(metadata).__qualname__
                )
            self["swordMetadataFormat"] = metadata_format
            self["swordMetadata"] = metadata.to_json()
            metadata.update_record_metadata(self)


pid_resolver = Resolver(
    pid_type="depid",
    object_type="rec",
    getter=functools.partial(SWORDDeposit.get_record, with_deleted=True),
)
