"""Single source of truth for the Disk Atlas version.

Read by the runtime (logged at startup, used by the future update check)
and by packaging/DiskAtlas.spec via exec() at build time.
"""

__version__ = "2.0.0"
APP_NAME = "Disk Atlas"
COMPANY_NAME = "Meruva"
BUNDLE_ID = "com.meruva.diskatlas"
