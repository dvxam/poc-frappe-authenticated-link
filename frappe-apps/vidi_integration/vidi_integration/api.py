"""Magic login links for Frappe LMS.

Two endpoints:
- create_magic_link : authenticated; mints a tokenised URL (returns URL only).
- magic_login       : guest; validates the token, logs the user in, redirects
                      to the course.

Security: only the SHA-256 hash of the token is stored; the raw token lives only
in the URL. TTL is enforced server-side. See the plan / README for the full
threat model (a reusable link is a bearer credential — use HTTPS in prod).
"""

import hashlib

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import add_days, get_url, now_datetime, get_datetime

DOCTYPE = "Magic Login Token"
MINT_ROLES = ("System Manager", "Magic Link Manager")


def _hash(raw_token: str) -> str:
    """SHA-256 of the raw token. What we store and look up by."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


@frappe.whitelist()
def create_magic_link(user, course=None, ttl_days=7, redirect_to=None):
    """Mint a magic login link for `user`.

    Authenticated + role-gated. Returns the URL and its expiry; does NOT send
    any email (the caller — e.g. Backstage — handles delivery).
    """
    frappe.only_for(MINT_ROLES)

    ttl_days = int(ttl_days)
    if ttl_days <= 0:
        frappe.throw(_("ttl_days must be a positive integer"))

    # User must already exist and be enabled (no auto-provisioning).
    if not frappe.db.exists("User", user):
        frappe.throw(_("User {0} does not exist").format(user))
    if not frappe.db.get_value("User", user, "enabled"):
        frappe.throw(_("User {0} is disabled").format(user))

    if course and not frappe.db.exists("LMS Course", course):
        frappe.throw(_("LMS Course {0} does not exist").format(course))

    raw_token = frappe.generate_hash(length=40)

    doc = frappe.get_doc(
        {
            "doctype": DOCTYPE,
            "token_hash": _hash(raw_token),
            "user": user,
            "course": course,
            "redirect_to": redirect_to,
            "expires_on": add_days(now_datetime(), ttl_days),
        }
    ).insert(ignore_permissions=True)

    magic_url = f"{get_url()}/api/method/vidi_integration.api.magic_login?token={raw_token}"
    return {"magic_url": magic_url, "expires_on": doc.expires_on, "name": doc.name}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=20, seconds=60 * 60)
def magic_login(token=None):
    """Consume a magic link: validate, log the user in, redirect to the course.

    On any failure we redirect to /login with a generic message — we never
    reveal whether the token was missing, expired or disabled.
    """
    try:
        _consume_and_login(token)
    except Exception:
        frappe.clear_messages()
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/login"


def _consume_and_login(token):
    if not token:
        raise frappe.ValidationError("missing token")

    name = frappe.db.get_value(DOCTYPE, {"token_hash": _hash(token)}, "name")
    if not name:
        raise frappe.ValidationError("unknown token")

    doc = frappe.get_doc(DOCTYPE, name)

    if doc.disabled:
        raise frappe.ValidationError("disabled token")
    if get_datetime(doc.expires_on) < now_datetime():
        raise frappe.ValidationError("expired token")

    # Start a real session for the target user. The login manager sets the
    # `sid` cookie on the response, so the browser is authenticated when it
    # follows the redirect below.
    frappe.local.login_manager.login_as(doc.user)

    doc.db_set("use_count", (doc.use_count or 0) + 1, update_modified=False)
    doc.db_set("last_used_on", now_datetime(), update_modified=False)
    frappe.db.commit()

    dest = doc.redirect_to or _course_destination(doc.course)
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = dest


def _course_destination(course):
    """Where a course-based link should land.

    Prefer the course's FIRST lesson (`/lms/courses/<course>/learn/1-1`) so the
    user starts the course directly instead of landing on the overview page and
    having to click "Continue Learning". Falls back to the course overview, then
    to the LMS home, if the outline can't be resolved.
    """
    if not course:
        return "/lms"
    try:
        from lms.lms.utils import get_lessons, get_lesson_url

        lessons = get_lessons(course)
        if lessons:
            url = get_lesson_url(course, lessons[0].number)
            if url:
                return url
    except Exception:
        pass
    return f"/lms/courses/{course}"
