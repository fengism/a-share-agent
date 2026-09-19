"""A-share agent backend package."""

import atexit as _atexit

from app.infrastructure.javascript_runtime import (
    install_legacy_mini_racer_shutdown_guard as _install_legacy_mini_racer_shutdown_guard,
)

# Lifespan startup installs this guard before normal AkShare usage. Keep an
# atexit fallback for scripts that import app modules without running FastAPI.
_atexit.register(_install_legacy_mini_racer_shutdown_guard)
