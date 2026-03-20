from __future__ import annotations

import argparse

import uvicorn
from services.hud.app.main import app as hud_app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Francis HUD as a single-process uvicorn server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--log-level", default="info")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    # Run the already-imported FastAPI app object so the HUD stays in-process on
    # Windows instead of spawning an extra import-string child.
    uvicorn.run(
        hud_app,
        host=str(args.host),
        port=int(args.port),
        log_level=str(args.log_level),
        reload=False,
        workers=1,
    )


if __name__ == "__main__":
    main()
