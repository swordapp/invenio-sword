from flask import url_for

from invenio_deposit.api import Deposit


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
