"""Browser checks with Playwright: move, win, undo, save, load, captured pieces.

Each test starts its own server in a temporary directory, so a real save file is
never touched. Run once before: python -m playwright install chromium
"""

import threading
from collections.abc import Callable, Iterator
from http.server import HTTPServer
from pathlib import Path

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import Page, expect

from server import make_server

StartServer = Callable[[], str]


@pytest.fixture
def start_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[StartServer]:
    """Start a fresh server (a fresh game) and return its URL; stop it after."""
    monkeypatch.chdir(tmp_path)
    servers: list[tuple[HTTPServer, threading.Thread]] = []

    def start() -> str:
        server = make_server(port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append((server, thread))
        return f"http://127.0.0.1:{server.server_port}"

    yield start
    for server, thread in servers:
        server.shutdown()
        server.server_close()
        thread.join()


def click_move(page: Page, source: str, target: str) -> None:
    page.click(f'[data-square="{source}"]')
    # Wait until the target is highlighted as a legal destination.
    expect(page.locator(f'[data-square="{target}"]')).to_contain_class("target")
    page.click(f'[data-square="{target}"]')


def play(page: Page, *moves: str) -> None:
    for move in moves:
        source, target = move.split("-")
        count = page.locator("#moves span").count()
        click_move(page, source, target)
        expect(page.locator("#moves span")).to_have_count(count + 1)


def square(page: Page, name: str):  # type: ignore[no-untyped-def]
    return page.locator(f'[data-square="{name}"]')


def test_move(page: Page, start_server: StartServer) -> None:
    page.goto(start_server())
    expect(page.locator("#turn")).to_have_text("White to move")

    page.click('[data-square="e2"]')
    expect(square(page, "e3")).to_have_class("square dark target")
    expect(square(page, "e4")).to_have_class("square light target")
    page.click('[data-square="e4"]')

    expect(square(page, "e4")).to_have_attribute("aria-label", "e4 White pawn")
    expect(square(page, "e2")).to_have_attribute("aria-label", "e2 empty")
    expect(page.locator("#moves span")).to_have_text(["e2-e4"])
    expect(page.locator("#turn")).to_have_text("Black to move")


def test_win(page: Page, start_server: StartServer) -> None:
    page.goto(start_server())
    play(page, "f2-f3", "e7-e5", "g2-g4", "d8-h4")

    expect(page.locator("#turn")).to_have_text("Checkmate. Black wins")
    expect(page.locator("#moves span").last).to_have_text("d8-h4#")
    expect(square(page, "e1")).to_contain_class("checked")


def test_undo(page: Page, start_server: StartServer) -> None:
    page.goto(start_server())
    play(page, "e2-e4", "d7-d5", "e4-d5")
    expect(square(page, "d5")).to_have_attribute("aria-label", "d5 White pawn")

    page.click('button[data-action="undo"]')
    expect(square(page, "d5")).to_have_attribute("aria-label", "d5 Black pawn")
    expect(square(page, "e4")).to_have_attribute("aria-label", "e4 White pawn")
    expect(page.locator("#moves span")).to_have_text(["e2-e4", "d7-d5"])
    expect(page.locator("#turn")).to_have_text("White to move")


def test_save(page: Page, start_server: StartServer) -> None:
    page.goto(start_server())
    play(page, "e2-e4", "e7-e5")
    page.click('button[data-action="save"]')
    expect(page.locator("#message")).to_have_text("Game saved")
    assert Path("game.save.json").exists()


def test_load_after_server_restart(page: Page, start_server: StartServer) -> None:
    page.goto(start_server())
    play(page, "e2-e4", "d7-d5", "e4-d5")
    page.click('button[data-action="save"]')
    expect(page.locator("#message")).to_have_text("Game saved")

    # A new server is a fresh game, as after a restart; the save file stays.
    page.goto(start_server())
    expect(page.locator("#moves span")).to_have_count(0)
    page.click('button[data-action="load"]')

    expect(page.locator("#message")).to_have_text("Game loaded")
    expect(page.locator("#moves span")).to_have_text(["e2-e4", "d7-d5", "e4xd5"])
    expect(square(page, "d5")).to_have_attribute("aria-label", "d5 White pawn")
    expect(page.locator("#turn")).to_have_text("Black to move")


def test_load_without_a_save_shows_an_error(
    page: Page, start_server: StartServer
) -> None:
    page.goto(start_server())
    play(page, "e2-e4")
    page.click('button[data-action="load"]')

    expect(page.locator("#message")).to_have_text("No saved game to load")
    expect(page.locator("#moves span")).to_have_text(["e2-e4"])
    expect(square(page, "e4")).to_have_attribute("aria-label", "e4 White pawn")


def test_captured_pieces_and_undo(page: Page, start_server: StartServer) -> None:
    page.goto(start_server())
    expect(page.locator("#captured")).to_have_text("None")
    play(page, "e2-e4", "d7-d5", "e4-d5")
    expect(page.locator("#captured .piece.black")).to_have_count(1)

    page.click('button[data-action="undo"]')
    expect(page.locator("#captured")).to_have_text("None")
