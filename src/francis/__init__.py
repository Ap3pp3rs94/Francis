from __future__ import annotations

from importlib import metadata

__all__ = ["__version__", "get_version"]


def get_version() -> str:
    """Return the package version, falling back to a development label."""
    try:
        return metadata.version("francis")
    except metadata.PackageNotFoundError:
        return "0.0.0+dev"


__version__ = get_version()
