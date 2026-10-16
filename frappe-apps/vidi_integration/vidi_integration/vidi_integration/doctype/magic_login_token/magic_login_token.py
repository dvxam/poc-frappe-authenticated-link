import frappe
from frappe.model.document import Document


class MagicLoginToken(Document):
    def validate(self):
        if not self.token_hash:
            frappe.throw("token_hash is required")
        if not self.expires_on:
            frappe.throw("expires_on is required")
