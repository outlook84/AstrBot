import logging
import ssl
import sys
from typing import Any

import aiohttp.connector as aiohttp_connector

from astrbot.utils.http_ssl_common import build_ssl_context_with_certifi

logger = logging.getLogger(__name__)


def configure_uvloop(log_obj: Any | None = None) -> bool:
    log = log_obj or logger

    if sys.platform == "win32":
        log.debug("uvloop is not supported on Windows; skipped.")
        return False

    try:
        import uvloop
    except ImportError:
        log.debug("uvloop is not installed; using default asyncio event loop.")
        return False

    try:
        uvloop.install()
    except Exception as exc:
        log.warning(
            "Failed to install uvloop; using default asyncio event loop: %r", exc
        )
        return False

    log.info("Using uvloop as the default asyncio event loop.")
    return True


def _try_patch_aiohttp_ssl_context(
    ssl_context: ssl.SSLContext,
    log_obj: Any | None = None,
) -> bool:
    log = log_obj or logger
    attr_name = "_SSL_CONTEXT_VERIFIED"

    if not hasattr(aiohttp_connector, attr_name):
        log.warning(
            "aiohttp connector does not expose _SSL_CONTEXT_VERIFIED; skipped patch.",
        )
        return False

    current_value = getattr(aiohttp_connector, attr_name, None)
    if current_value is not None and not isinstance(current_value, ssl.SSLContext):
        log.warning(
            "aiohttp connector exposes _SSL_CONTEXT_VERIFIED with unexpected type; skipped patch.",
        )
        return False

    setattr(aiohttp_connector, attr_name, ssl_context)
    log.info("Configured aiohttp verified SSL context with system+certifi trust chain.")
    return True


def configure_runtime_ca_bundle(log_obj: Any | None = None) -> bool:
    log = log_obj or logger

    try:
        log.info("Bootstrapping runtime CA bundle.")
        ssl_context = build_ssl_context_with_certifi(log_obj=log)
        return _try_patch_aiohttp_ssl_context(ssl_context, log_obj=log)
    except Exception as exc:
        log.error("Failed to configure runtime CA bundle for aiohttp: %r", exc)
        return False


def initialize_runtime_bootstrap(log_obj: Any | None = None) -> bool:
    configure_uvloop(log_obj=log_obj)
    return configure_runtime_ca_bundle(log_obj=log_obj)
