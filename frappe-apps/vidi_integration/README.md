# vidi_integration

Custom Frappe app for the VIDI SI platform.

Provides **magic login links** for Frappe LMS: an authenticated caller mints a
tokenised URL (TTL, default 7 days) that, when opened, logs the target user in
and redirects them to a course. See `vidi_integration/api.py`.
