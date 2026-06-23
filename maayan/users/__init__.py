"""User accounts, authentication, and sessions (auth / multi-user layer).

Off by default (`auth_enabled=false`) so local dev and the existing test suite are
unchanged; the cloud deploy turns it on to put a login wall in front of the UI and let an
admin create/manage users. See docs/cloud_deploy/02_USER_MANAGEMENT.md.
"""
