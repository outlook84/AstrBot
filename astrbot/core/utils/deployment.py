import os
from pathlib import Path

from astrbot.core.utils.bool_parser import parse_bool


def is_containerized_runtime() -> bool:
    """Best-effort detection for Docker/Kubernetes style deployments."""
    explicit = os.environ.get("ASTRBOT_CONTAINERIZED")
    if explicit is not None:
        return parse_bool(explicit, False)

    if os.environ.get("KUBERNETES_SERVICE_HOST"):
        return True

    if Path("/.dockerenv").exists():
        return True

    return False
