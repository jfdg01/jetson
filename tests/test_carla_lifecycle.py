"""Close the UI, launch it again -- the bug was that this needed a manual pkill.

Opt-in: boots a real CARLA twice (~20 s, needs the GPU), so `make test` skips it.

    CARLA_LIFECYCLE_TEST=1 .venv-ft/bin/python -m pytest tests/test_carla_lifecycle.py -s
"""
import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("carla")
if not os.environ.get("CARLA_LIFECYCLE_TEST"):
    pytest.skip("set CARLA_LIFECYCLE_TEST=1 -- boots a real CARLA",
                allow_module_level=True)

_p = Path(__file__).resolve().parent.parent / "runners" / "carla_debug_ui.py"
_spec = importlib.util.spec_from_file_location("carla_debug_ui", _p)
ui = importlib.util.module_from_spec(_spec)
sys.modules["carla_debug_ui"] = ui
_spec.loader.exec_module(ui)

PORT = 2000


def test_close_then_relaunch_needs_no_manual_kill():
    if subprocess.run(["pgrep", "-f", "CarlaUE4-Linux-Shipping"],
                      capture_output=True).returncode == 0:
        pytest.skip("a CARLA is already running -- this test owns the port")
    for i in (1, 2):
        t0 = time.time()
        client, proc = ui.ensure_carla("127.0.0.1", PORT, ui.CARLA_SH)
        took = time.time() - t0
        # proc is None only when it connected to a server it did not start -- i.e.
        # the previous iteration's server was still alive
        assert proc is not None, f"launch {i} found a server it should have stopped"
        # the symptom being regression-tested: a stale server holding the port made
        # this sit in the wait loop until the 300 s timeout
        assert took < 120, f"launch {i} took {took:.0f}s -- the hang is back"
        assert client.get_server_version()
        ui.stop_carla(proc)
        # the port, not the process list: a sibling UE4 helper can outlive the
        # group by a few seconds, and it blocks nothing. Holding the port does.
        assert ui.port_owner(PORT)[0] is None, f"port {PORT} still held after close"


def test_ctrl_c_exits_clean():
    """SIGINT used to land inside tick(), destroy the widgets, and return into the
    half-finished callback: 'invalid command name .!frame.!scale'. Exit code and
    stderr are the assertion -- the traceback was printed, not raised."""
    if not os.environ.get("DISPLAY"):
        pytest.skip("needs an X display -- this opens the real window")
    if subprocess.run(["pgrep", "-f", "CarlaUE4-Linux-Shipping"],
                      capture_output=True).returncode == 0:
        pytest.skip("a CARLA is already running -- this test owns the port")
    p = subprocess.Popen([sys.executable, str(_p)], stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True)
    try:
        time.sleep(60)                      # boot CARLA, open the window, run ticks
        assert p.poll() is None, "died before we could interrupt it"
        p.send_signal(2)                    # SIGINT, same as Ctrl+C
        out = p.communicate(timeout=60)[0]
    finally:
        if p.poll() is None:
            p.kill()
    assert p.returncode == 0, f"exit {p.returncode}\n{out}"
    assert "Traceback" not in out, f"crashed on the way out:\n{out}"
    assert "invalid command name" not in out, f"dead-widget access is back:\n{out}"
    assert ui.port_owner(PORT)[0] is None, f"port {PORT} still held after Ctrl+C"


def test_port_owner_reads_a_listening_socket():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    pid, name = ui.port_owner(s.getsockname()[1])
    s.close()
    assert pid == os.getpid() and "python" in name.lower()
