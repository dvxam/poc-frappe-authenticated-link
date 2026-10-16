import frappe
from frappe.core.doctype.user.user import generate_keys

MAGIC_LINK_MANAGER_ROLE = "Magic Link Manager"
DEFAULT_SERVICE_USER = "svc-magic-link@vidi.local"


def after_install():
    """Ensure the custom role used to gate magic-link minting exists."""
    if not frappe.db.exists("Role", MAGIC_LINK_MANAGER_ROLE):
        frappe.get_doc(
            {
                "doctype": "Role",
                "role_name": MAGIC_LINK_MANAGER_ROLE,
                "desk_access": 0,
            }
        ).insert(ignore_permissions=True)
        frappe.db.commit()


def ensure_service_user(email=DEFAULT_SERVICE_USER):
    """Create (idempotently) a least-privilege service user for minting links
    and (re)generate its API key/secret.

    The user is API-only: a System User holding ONLY the `Magic Link Manager`
    role (which has no desk access), no password, no welcome email. Callers
    (e.g. Backstage) authenticate with `Authorization: token <key>:<secret>`.

    Returns {user, api_key, api_secret}. NOTE: `api_secret` is only readable at
    generation time, so capture it now. Re-running rotates the secret.
    """
    after_install()

    if not frappe.db.exists("User", email):
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": "Magic Link Service",
                "user_type": "System User",
                "enabled": 1,
                "send_welcome_email": 0,
            }
        )
        user.flags.no_welcome_mail = True
        user.insert(ignore_permissions=True)
        user.add_roles(MAGIC_LINK_MANAGER_ROLE)

    keys = generate_keys(email)  # {"api_key": ..., "api_secret": ...}
    frappe.db.commit()

    return {
        "user": email,
        "api_key": frappe.db.get_value("User", email, "api_key"),
        "api_secret": keys["api_secret"],
    }
