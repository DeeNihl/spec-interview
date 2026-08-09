"""Command-line interface."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table

from spec_interview.config import AppConfig, ConversationProviderFactory, ProviderName
from spec_interview.conversation.manager import ConversationManager
from spec_interview.conversation.models import ProviderStatus, ResponseInterrupted
from spec_interview.conversation.provider import ProviderUnavailableError
from spec_interview.sessions import SessionStore

app = typer.Typer(help="Conduct and preserve provider-neutral technical interviews.")
providers_app = typer.Typer(help="Inspect conversation providers.")
sessions_app = typer.Typer(help="Inspect saved interview sessions.")
devices_app = typer.Typer(help="Inspect optional audio devices.")
app.add_typer(providers_app, name="providers")
app.add_typer(sessions_app, name="sessions")
app.add_typer(devices_app, name="devices")
console = Console()


def _config(data_dir: Path | None = None) -> AppConfig:
    config = AppConfig()
    return config.model_copy(update={"data_dir": data_dir}) if data_dir else config


async def _statuses(config: AppConfig) -> list[ProviderStatus]:
    return [
        await ConversationProviderFactory.create(name, config).status()
        for name in ConversationProviderFactory.names()
    ]


@providers_app.command("list")
def providers_list(
    plain: Annotated[bool, typer.Option("--plain", help="Use machine-friendly JSON.")] = False,
) -> None:
    """List providers, capabilities, and current availability."""
    statuses = asyncio.run(_statuses(AppConfig()))
    if plain:
        typer.echo(json.dumps([status.model_dump(mode="json") for status in statuses], indent=2))
        return
    table = Table(title="Conversation providers")
    table.add_column("Provider")
    table.add_column("Available")
    table.add_column("Capabilities")
    table.add_column("Detail")
    for status in statuses:
        capabilities = ", ".join(
            key for key, enabled in status.capabilities.model_dump().items() if enabled
        )
        table.add_row(status.name, "yes" if status.available else "no", capabilities, status.detail)
    console.print(table)


@devices_app.command("list")
def devices_list() -> None:
    """List audio devices when the optional audio extra is installed."""
    try:
        import sounddevice  # type: ignore[import-not-found]
    except ImportError:
        typer.echo("Audio device discovery unavailable; install spec-interview[audio].")
        raise typer.Exit(code=2) from None
    typer.echo(str(sounddevice.query_devices()))


@app.command("doctor")
def doctor(
    plain: Annotated[bool, typer.Option("--plain", help="Use machine-friendly JSON.")] = False,
) -> None:
    """Check provider prerequisites without starting a session."""
    statuses = asyncio.run(_statuses(AppConfig()))
    if plain:
        typer.echo(json.dumps([status.model_dump(mode="json") for status in statuses], indent=2))
    else:
        for status in statuses:
            icon = "OK" if status.available else "--"
            typer.echo(f"[{icon}] {status.name}: {status.detail}")


async def _start_session(
    provider_name: ProviderName,
    message: str,
    data_dir: Path | None,
    interrupt_after: float | None,
) -> tuple[UUID, str]:
    config = _config(data_dir)
    provider = ConversationProviderFactory.create(provider_name, config)
    manager = ConversationManager(provider, SessionStore(config.data_dir))
    await manager.start()
    before = manager.last_sequence
    await manager.send_text(message)
    if interrupt_after is not None:
        await asyncio.sleep(interrupt_after)
        await manager.interrupt()
    terminal = await manager.wait_for_response(before)
    await manager.create_checkpoint()
    summary = await manager.close()
    result = "interrupted" if isinstance(terminal.payload, ResponseInterrupted) else "completed"
    return summary.session_id, result


@app.command("start")
def start(
    provider: Annotated[ProviderName, typer.Option("--provider")] = "mock",
    message: Annotated[str, typer.Option("--message")] = "Describe the system boundary.",
    data_dir: Annotated[Path | None, typer.Option("--data-dir")] = None,
    interrupt_after: Annotated[
        float | None,
        typer.Option("--interrupt-after", min=0.0, help="Interrupt after N seconds."),
    ] = None,
    plain: Annotated[bool, typer.Option("--plain")] = False,
) -> None:
    """Start one interview turn and persist its complete event history."""
    try:
        session_id, result = asyncio.run(
            _start_session(provider, message, data_dir, interrupt_after)
        )
    except ProviderUnavailableError as error:
        typer.echo(f"Provider unavailable: {error}", err=True)
        raise typer.Exit(code=2) from None
    if plain:
        typer.echo(json.dumps({"session_id": str(session_id), "result": result}))
    else:
        console.print(f"Session [bold]{session_id}[/bold] {result}; checkpoint and views saved.")


async def _resume_session(
    session_id: UUID,
    message: str,
    data_dir: Path | None,
) -> str:
    config = _config(data_dir)
    store = SessionStore(config.data_dir)
    checkpoint = store.read_checkpoint(session_id)
    provider_name = checkpoint.provider
    if provider_name not in ConversationProviderFactory.names():
        raise ValueError(f"unsupported checkpoint provider: {provider_name}")
    provider = ConversationProviderFactory.create(provider_name, config)
    manager = ConversationManager(provider, store, session_id=session_id)
    await manager.resume()
    before = manager.last_sequence
    await manager.send_text(message)
    terminal = await manager.wait_for_response(before)
    await manager.create_checkpoint()
    await manager.close()
    return terminal.payload.type


@app.command("resume")
def resume(
    session_id: UUID,
    message: Annotated[str, typer.Option("--message")] = "What assumption is most fragile?",
    data_dir: Annotated[Path | None, typer.Option("--data-dir")] = None,
    plain: Annotated[bool, typer.Option("--plain")] = False,
) -> None:
    """Resume a checkpointed session under the same stable interview ID."""
    result = asyncio.run(_resume_session(session_id, message, data_dir))
    if plain:
        typer.echo(json.dumps({"session_id": str(session_id), "terminal_event": result}))
    else:
        console.print(f"Session [bold]{session_id}[/bold] resumed; {result}.")


@app.command("transcript")
def transcript(
    session_id: UUID,
    data_dir: Annotated[Path | None, typer.Option("--data-dir")] = None,
) -> None:
    """Regenerate and print a transcript from normalized events."""
    store = SessionStore(_config(data_dir).data_dir)
    typer.echo(store.render_transcript(session_id), nl=False)


@sessions_app.command("list")
def sessions_list(
    data_dir: Annotated[Path | None, typer.Option("--data-dir")] = None,
    plain: Annotated[bool, typer.Option("--plain")] = False,
) -> None:
    """List saved sessions in most-recent-first order."""
    store = SessionStore(_config(data_dir).data_dir)
    sessions = store.list_sessions()
    if plain:
        typer.echo(json.dumps([str(session_id) for session_id in sessions]))
        return
    for session_id in sessions:
        events = store.read_events(session_id)
        typer.echo(f"{session_id}  events={len(events)}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
