"""Coretact - Meshcore Contact Management System."""

import os

import sentry_sdk
from sentry_sdk.scrubber import DEFAULT_DENYLIST, EventScrubber

from coretact.version import __version__

# Prevent sensitive environment variables from being sent to Sentry
denylist = DEFAULT_DENYLIST + [
    "DISCORD_BOT_TOKEN",
    "DISCORD_BOT_OWNER_ID",
]

sentry_sdk.init(
    send_default_pii=False,
    release=f"coretact@{__version__}",
    traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", 0.1)),
    profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", 0.1)),
    event_scrubber=EventScrubber(denylist=denylist, recursive=True),
)
