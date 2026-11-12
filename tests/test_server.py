import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

import pytest

from server import make_server


@pytest.fixture
def base_url() -> Iterator[str]:
    server = make_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def request(url: str, body: bytes | None = None) -> tuple[int, Any]:
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        with error:
            return error.code, json.loads(error.read())


def test_action_that_is_not_an_object_is_rejected(base_url: str) -> None:
    code, body = request(f"{base_url}/api/action", json.dumps([1, 2]).encode())
    assert code == 400
    assert body["error"] == "Expected an action object"


def test_move_action_is_played(base_url: str) -> None:
    action = {"action": "move", "source": "e2", "target": "e4"}
    code, body = request(f"{base_url}/api/action", json.dumps(action).encode())
    assert code == 200
    assert body["moves"] == ["e2-e4"]
    assert body["turn"] == "b"


def test_state_is_served(base_url: str) -> None:
    code, body = request(f"{base_url}/api/state")
    assert code == 200
    assert body["moves"] == []
    assert body["turn"] == "w"
