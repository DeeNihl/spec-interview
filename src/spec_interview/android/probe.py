"""Non-mutating Android/Termux capability and model inventory probe."""

from __future__ import annotations

import asyncio
import shutil
from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from spec_interview.providers.gemma import GemmaTransport


class CommandResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    returncode: int
    stdout: str = ""
    stderr: str = ""


class CommandRunner(Protocol):
    async def __call__(self, command: Sequence[str]) -> CommandResult: ...


class ProbeCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    available: bool
    detail: str


class AndroidProbeReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    architecture: str
    android_version: str | None = None
    device: str | None = None
    matching_packages: list[str] = Field(default_factory=list)
    registered_models: list[str] = Field(default_factory=list)
    checks: list[ProbeCheck] = Field(default_factory=list)


async def run_command(command: Sequence[str]) -> CommandResult:
    executable = shutil.which(command[0])
    if executable is None:
        return CommandResult(returncode=127, stderr=f"{command[0]} not found")
    process = await asyncio.create_subprocess_exec(
        executable,
        *command[1:],
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return CommandResult(
        returncode=process.returncode or 0,
        stdout=stdout.decode(errors="replace").strip(),
        stderr=stderr.decode(errors="replace").strip(),
    )


class AndroidProbe:
    """Inspect device facts without changing packages, permissions, or files."""

    def __init__(self, transport: GemmaTransport, runner: CommandRunner = run_command) -> None:
        self.transport = transport
        self.runner = runner

    async def inspect(self) -> AndroidProbeReport:
        architecture, version, device, packages, microphone = await asyncio.gather(
            self.runner(("uname", "-m")),
            self.runner(("getprop", "ro.build.version.release")),
            self.runner(("getprop", "ro.product.model")),
            self.runner(("pm", "list", "packages")),
            self.runner(("termux-microphone-record", "-h")),
        )
        checks = [
            ProbeCheck(
                name="android-properties",
                available=version.returncode == 0,
                detail=version.stderr or version.stdout or "Android properties unavailable",
            ),
            ProbeCheck(
                name="termux-microphone-record",
                available=microphone.returncode == 0,
                detail=(
                    "Termux:API microphone command available"
                    if microphone.returncode == 0
                    else microphone.stderr or "microphone command unavailable"
                ),
            ),
        ]
        try:
            models = list(await self.transport.list_models())
        except Exception as error:  # probe must preserve every other diagnostic
            models = []
            checks.append(
                ProbeCheck(
                    name="gemma-server",
                    available=False,
                    detail=f"local model server unavailable: {error}",
                )
            )
        else:
            checks.append(
                ProbeCheck(
                    name="gemma-server",
                    available=True,
                    detail=f"registered models: {', '.join(models) if models else 'none'}",
                )
            )

        package_matches = sorted(
            line.removeprefix("package:")
            for line in packages.stdout.splitlines()
            if any(
                token in line.casefold() for token in ("gemma", "ai.edge", "aiedge", "termux.api")
            )
        )
        return AndroidProbeReport(
            architecture=architecture.stdout or "unknown",
            android_version=version.stdout or None,
            device=device.stdout or None,
            matching_packages=package_matches,
            registered_models=models,
            checks=checks,
        )
