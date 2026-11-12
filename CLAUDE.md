# Project instructions

## Checks before reporting any task as done

Run all three and make sure they pass:

```sh
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

On Mac/Linux use `.venv/bin/python` instead of `.\.venv\Scripts\python.exe`.

Also run `.\.venv\Scripts\python.exe -m mypy --strict .` and report the results. It is not
required to pass on the existing untyped code, but new code gets type annotations.

## Tests

- Write tests through `Session.dispatch` (for example `{"action": "undo"}`), not by reading
  or setting internal fields.
- Expected results come from the requirements and the team design, never from what the
  code currently does.
- Never change or delete an existing test to make it pass. If a test fails, report it and
  explain why.
- Show each new test failing before implementing the behavior.

## Team design

- `Session` stores `self.moves = [(source, target, promotion), ...]` (`promotion` is
  `None` if there was none) and `self.redo = []`.
- `self.position` and `self.notation` are rebuilt by replaying `self.moves` from
  `new_position()`.
- Every new `Session` field must be set in `__init__`, because "new game" resets through
  `__init__`.
- Undo against the computer removes moves until it's the player's turn again (at least one
  of the player's moves). Redo restores the same moves, including the same computer reply.
- Undo/redo with nothing to do: nothing happens, no error.
- Save file: `game.save.json` with `{"opponent", "moves", "redo"}`. A missing or invalid
  file shows an error and leaves the current game unchanged.

## Environment

- Never change Windows security settings (for example, the execution policy).
- Don't activate the venv; call the venv's python directly.
