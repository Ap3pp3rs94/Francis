from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

typer: Any | None
try:
    import typer
except Exception:  # pragma: no cover - optional dependency
    typer = None

rich_print: Callable[..., Any]

try:
    from rich import print as rich_print
except Exception:  # pragma: no cover - optional dependency
    rich_print = print

logger = logging.getLogger(__name__)

_cli_pkg = Path(__file__).with_name("cli")
if _cli_pkg.is_dir():
    __path__ = [str(_cli_pkg)]  # type: ignore[var-annotated]


class _FallbackApp:
    def command(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            return fn

        return decorator

    def __call__(self) -> None:
        rich_print("Typer not installed; CLI commands unavailable.")


app = typer.Typer(help="Francis 2.0 CLI") if typer is not None else _FallbackApp()


@app.command()
def doctor() -> int:
    try:
        from francis.kernel.health import health_report
    except Exception as exc:
        logger.error("Health report import failed: %s", exc)
        rich_print("[red]Health report unavailable[/red]")
        return 1

    rich_print("[green]OK[/green] Francis CLI alive.")
    try:
        rich_print(health_report())
    except Exception as exc:
        logger.error("Health report failed: %s", exc)
        rich_print("[red]Health report failed[/red]")
        return 1
    return 0


@app.command()
def api(host: str = "127.0.0.1", port: int = 8000) -> int:
    try:
        import uvicorn
    except Exception as exc:
        logger.error("uvicorn import failed: %s", exc)
        rich_print("[red]uvicorn not available[/red]")
        return 1

    try:
        from francis.api.app import create_app
    except Exception as exc:
        logger.error("API app import failed: %s", exc)
        rich_print("[red]API app unavailable[/red]")
        return 1

    uvicorn.run(create_app(), host=host, port=port, log_level="info")
    return 0


@app.command()
def daemon() -> int:
    try:
        from francis.daemon.runner import run_daemon
    except Exception as exc:
        logger.error("Daemon import failed: %s", exc)
        rich_print("[red]Daemon unavailable[/red]")
        return 1

    try:
        result = run_daemon()
    except Exception as exc:
        logger.error("Daemon failed: %s", exc)
        rich_print("[red]Daemon failed[/red]")
        return 1
    if isinstance(result, int):
        return int(result)
    return 0


def main() -> int:
    try:
        app()
        return 0
    except Exception as exc:
        logger.error("CLI failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
