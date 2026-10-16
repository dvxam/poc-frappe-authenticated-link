app_name = "vidi_integration"
app_title = "Vidi Integration"
app_publisher = "VIDI"
app_description = "Magic login links for Frappe LMS courses"
app_email = "it@vidi.local"
app_license = "mit"

# Ensure the "Magic Link Manager" role exists after install/migrate.
after_install = "vidi_integration.setup.after_install"
after_migrate = "vidi_integration.setup.after_install"
