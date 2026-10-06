from pydantic import ValidationError
import pytest

from src import api


def test_health() -> None:
    assert api.health()["status"] == "ok"


def test_task_request_bounds() -> None:
    assert api.TaskRequest(request="hello").input_channel == "text"
    with pytest.raises(ValidationError):
        api.TaskRequest(request="")
