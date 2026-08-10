from __future__ import annotations

import json

from typer.testing import CliRunner

from spec_interview.cli.app import app

runner = CliRunner()


def test_provider_list_plain() -> None:
    result = runner.invoke(app, ["providers", "list", "--plain"])
    assert result.exit_code == 0
    providers = json.loads(result.stdout)
    assert [provider["name"] for provider in providers] == [
        "mock",
        "gemma-local",
        "parlor-gemma",
        "nova-sonic",
    ]


def test_android_spoken_commands_are_registered() -> None:
    tts = runner.invoke(app, ["android", "tts-test", "--help"])
    converse = runner.invoke(app, ["android", "converse", "--help"])

    assert tts.exit_code == 0, tts.output
    assert "Android system TTS" in tts.output
    assert converse.exit_code == 0, converse.output
    assert "multi-turn spoken specification interview" in converse.output


def test_cli_start_resume_and_transcript(tmp_path) -> None:
    started = runner.invoke(
        app,
        [
            "start",
            "--provider",
            "mock",
            "--message",
            "Map the data flow",
            "--data-dir",
            str(tmp_path),
            "--plain",
        ],
    )
    assert started.exit_code == 0, started.output
    session_id = json.loads(started.stdout)["session_id"]

    resumed = runner.invoke(
        app,
        [
            "resume",
            session_id,
            "--message",
            "Challenge the boundary",
            "--data-dir",
            str(tmp_path),
            "--plain",
        ],
    )
    assert resumed.exit_code == 0, resumed.output

    transcript = runner.invoke(app, ["transcript", session_id, "--data-dir", str(tmp_path)])
    assert transcript.exit_code == 0
    assert "You: Map the data flow" in transcript.stdout
    assert "You: Challenge the boundary" in transcript.stdout


def test_cli_interrupts_response(tmp_path) -> None:
    result = runner.invoke(
        app,
        [
            "start",
            "--provider",
            "mock",
            "--message",
            "This response should be interrupted",
            "--interrupt-after",
            "0.015",
            "--data-dir",
            str(tmp_path),
            "--plain",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["result"] == "interrupted"
