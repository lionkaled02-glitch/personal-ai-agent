import pytest
from pydantic import ValidationError

from src import api


def test_health() -> None:
    assert api.health()["status"] == "ok"


def test_task_request_bounds() -> None:
    assert api.TaskRequest(request="hello").input_channel == "text"
    with pytest.raises(ValidationError):
        api.TaskRequest(request="")
    with pytest.raises(ValidationError):
        api.TaskRequest(request="x" * 20_001)


def test_api_list_bounds() -> None:
    with pytest.raises(api.HTTPException):
        api.list_tasks(0)
    with pytest.raises(api.HTTPException):
        api.list_tasks(501)
    with pytest.raises(api.HTTPException):
        api.get_events("missing", 0)
