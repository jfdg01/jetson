"""Session-limit backoff in scripts/autoresearch.py (the 5h-window guard).

Fixture string is the verbatim tail of .claude/autoresearch-logs/cycle-1784522401.log
from the 2026-07-20 unattended run.
"""
import datetime
import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "autoresearch", pathlib.Path(__file__).parent.parent / "scripts" / "autoresearch.py")
ar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ar)

REAL = "You've hit your session limit · resets 9:40am (Europe/Madrid)\n"
TZ = datetime.timezone(datetime.timedelta(hours=2))


def at(h, m):
    return datetime.datetime(2026, 7, 20, h, m, tzinfo=TZ)


def test_parses_reset_time():
    assert ar.session_limit_reset(REAL, now=at(6, 40)) == at(9, 40)


def test_reset_already_past_rolls_to_tomorrow():
    # limit hit at 10:00pm, resets 1:00am -> next day, not 16h in the past
    txt = "You've hit your session limit · resets 1:00am (Europe/Madrid)\n"
    assert ar.session_limit_reset(txt, now=at(22, 0)) == at(1, 0) + datetime.timedelta(days=1)


def test_ignores_ordinary_failure():
    assert ar.session_limit_reset("Traceback ...\nValueError: boom\n", now=at(6, 40)) is None


def test_ignores_the_phrase_far_from_the_tail():
    # driver quoting an old log mid-cycle must not park the loop for a day
    assert ar.session_limit_reset(REAL + "x" * 600, now=at(6, 40)) is None


def test_unparseable_park_file_fails_open(tmp_path, monkeypatch):
    p = tmp_path / "resume-at"
    p.write_text("not a timestamp")
    monkeypatch.setattr(ar, "RESUME_AT", p)
    assert ar.parked_until() == 0
    p.write_text(at(9, 40).isoformat())
    assert ar.parked_until() == at(9, 40).timestamp()


if __name__ == "__main__":
    import pytest, sys
    sys.exit(pytest.main([__file__, "-q"]))
