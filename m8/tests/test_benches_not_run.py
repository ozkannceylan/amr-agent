"""Plant benches refuse to invent a number when the plant is absent."""
import runpy
import sys
from pathlib import Path

import pytest

_BENCH = Path(__file__).resolve().parents[1] / "bench"
_SCRIPTS = ("e1_pocket.py", "e3_abort.py", "e4_slot.py", "e5_cost.py")


@pytest.mark.parametrize("name", _SCRIPTS)
def test_bench_prints_not_run_and_exits_2(name, capsys, monkeypatch):
    # A plant session exports GZ_PARTITION; pytest is not one. Without it
    # every bench must say NOT_RUN even while a plant runs beside it.
    monkeypatch.delenv("GZ_PARTITION", raising=False)
    path = _BENCH / name
    with pytest.raises(SystemExit) as caught:
        runpy.run_path(str(path), run_name="__main__")
    assert caught.value.code == 2
    out = capsys.readouterr().out
    assert "NOT_RUN" in out
    assert "did not" in out.lower() or "not scored" in out.lower() \
        or "not compute" in out.lower() or "not publish" in out.lower() \
        or "not synthesize" in out.lower()
    # A stub that printed a fake rms would fail this.
    assert "0.0706" not in out or name == "e1_pocket.py"
    if name == "e1_pocket.py":
        assert "quoted" in out.lower() or "bar" in out.lower()
