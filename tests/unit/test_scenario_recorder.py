import pytest

from qa_manager.services.scenario_recorder import RECORDER_SCRIPT, Recording, ScenarioRecorderService, validate_wait


def test_wait_validation_defaults_and_rejects_invalid_values():
    assert validate_wait({"selector": " #ready "}) == {
        "action": "wait", "selector": "#ready", "state": "visible", "timeout": 10000
    }
    with pytest.raises(ValueError, match="Invalid wait state"):
        validate_wait({"selector": "body", "state": "moving"})
    with pytest.raises(ValueError, match="between"):
        validate_wait({"selector": "body", "timeout": 0})


def test_recorder_script_redacts_secrets_and_uses_locator_priority():
    assert "data-testid" in RECORDER_SCRIPT
    assert RECORDER_SCRIPT.index("data-testid") < RECORDER_SCRIPT.index("getAttribute('role')")
    assert RECORDER_SCRIPT.index("getAttribute('role')") < RECORDER_SCRIPT.index("el.labels")
    assert "el.type === 'password'" in RECORDER_SCRIPT
    assert "SECRET:" in RECORDER_SCRIPT


def test_wait_can_be_added_to_draft_without_starting_browser():
    service = ScenarioRecorderService()
    recording = Recording("recording-id", "project-id", "http://localhost")
    service._recordings[recording.id] = recording
    result = service.command(recording.id, "add_wait", {"selector": "main", "state": "hidden", "timeout": 250})
    assert result["steps"] == [{"action": "wait", "selector": "main", "state": "hidden", "timeout": 250}]
