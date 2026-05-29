from __future__ import annotations

import logging

_LOG = logging.getLogger("francis.lens.errors")


def lens_error_code(exc: BaseException, *, code: str = "internal_api_error", surface: str = "") -> str:
    surface_text = f" surface={surface}" if surface else ""
    _LOG.exception("Lens boundary exception%s", surface_text, exc_info=(type(exc), exc, exc.__traceback__))
    return code
