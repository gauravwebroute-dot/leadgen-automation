import logging
import xmlrpc.client

from app.config import settings

logger = logging.getLogger(__name__)


class OdooClientError(Exception):
    """Raised when Odoo auth or a CRM write fails."""


class OdooClient:
    def __init__(self):
        if not all([settings.odoo_url, settings.odoo_db, settings.odoo_username, settings.odoo_api_key]):
            raise OdooClientError(
                "Odoo credentials not configured — set ODOO_URL, ODOO_DB, "
                "ODOO_USERNAME and ODOO_API_KEY in .env"
            )

        self.url = settings.odoo_url.rstrip("/")
        self.db = settings.odoo_db
        self.username = settings.odoo_username
        self.password = settings.odoo_api_key
        self._uid = None

    def _authenticate(self) -> int:
        if self._uid:
            return self._uid

        common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
        try:
            uid = common.authenticate(self.db, self.username, self.password, {})
        except Exception as e:
            raise OdooClientError(f"Odoo authentication request failed: {e}")

        if not uid:
            raise OdooClientError("Odoo authentication rejected — check ODOO_DB/USERNAME/API_KEY")

        self._uid = uid
        return uid

    def create_lead(self, name: str, company: str, title: str, phone: str, email: str, source_note: str) -> int:
        uid = self._authenticate()
        models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")

        try:
            lead_id = models.execute_kw(
                self.db,
                uid,
                self.password,
                "crm.lead",
                "create",
                [
                    {
                        "name": f"{name} - {company}".strip(" -"),
                        "contact_name": name,
                        "partner_name": company,
                        "function": title,
                        "phone": phone or "",
                        "email_from": email or "",
                        "description": source_note,
                    }
                ],
            )
        except Exception as e:
            raise OdooClientError(f"Failed to create Odoo lead for '{name}': {e}")

        logger.info("Created Odoo lead %s for %s at %s", lead_id, name, company)
        return lead_id
