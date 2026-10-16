"""Fix SCORM chapters answering 403 to everyone (Frappe LMS bug).

On upload, LMS extracts a package to private/scorm/<course>/<chapter.name>/ and stores
launch_file = /scorm/<course>/<chapter.name>/index.html. But SCORMRenderer._check_permission
reads that same path segment as the chapter *title* ({"course": course, "title": segment}).
Course Chapter is named "format:{####} {title}" (e.g. "0017 Phishing" vs title "Phishing"),
so the lookup never matches, every package file raises PermissionError, and the player
iframe shows an error instead of the course.

This patch makes the gate resolve the segment as the chapter name first, then falls back
to the title (legacy packages extracted under the title). All the access rules after the
lookup (enrolment, sequential locking) are unchanged.

A page_renderer hook cannot override it: renderers are tried in app install order and lms
comes first. The patch is applied from a before_request hook, so it holds on every worker.
"""

from urllib.parse import unquote

import frappe

_PATCHED = False


def _check_permission(self):
	from lms.lms.doctype.course_chapter.course_chapter import (
		get_scorm_lesson,
		resolve_scorm_access,
	)

	parts = self.path.strip("/").split("/")
	# scorm/<course>/<chapter name or title>/...
	if len(parts) < 3 or parts[0] != "scorm":
		raise frappe.PermissionError
	course, segment = unquote(parts[1]), unquote(parts[2])

	chapter = frappe.db.get_value(
		"Course Chapter", {"course": course, "name": segment, "is_scorm_package": 1}, "name"
	) or frappe.db.get_value(
		"Course Chapter", {"course": course, "title": segment, "is_scorm_package": 1}, "name"
	)
	if not chapter:
		raise frappe.PermissionError

	access = resolve_scorm_access(course, get_scorm_lesson(chapter))
	if not access.can_access or access.locked:
		frappe.logger("lms.security").warning(
			"SCORM resource access denied: user=%s path=%s", frappe.session.user, self.path
		)
		raise frappe.PermissionError


def apply():
	global _PATCHED
	if _PATCHED:
		return
	try:
		from lms.page_renderers import SCORMRenderer
	except ImportError:
		return
	SCORMRenderer._check_permission = _check_permission
	_PATCHED = True
