#!/usr/bin/env python3
"""Live Orin device telemetry for the panel's ORIN dashboard: watts, tj, GPU, RAM.

The panel already reports what the Orin *does* (ground ms, carry Hz). This is what it
*costs*, which is the P6.6 axis: `experiments/2026-07-25-maintain-cost/` measured the
deployed carry at 10.84 W against a 5.19 W idle floor, and until now there was no way
to see that live while flying.

**sysfs, not `tegrastats`.** tegrastats is effectively a singleton -- starting one wants
`tegrastats --stop` first, and a power campaign owns that process for its whole run, so a
panel that started its own would either fail or stomp the measurement. Reading the INA3221
rails and the thermal zones straight out of sysfs is passive: one `cat` per second over a
single persistent ssh, no process to own, nothing to stop. P6.6's own numbers come off the
same rails via tegrastats, so the readings are comparable by construction.

Run standalone to check the device and the parser:

    .venv-ft/bin/python runners/orin_telemetry.py           # 5 s of live samples
"""
import subprocess
import threading
import time

HOST = "jetson"
PERIOD_S = 1.0
# Resolve the paths ON the device (the hwmon index moves across boots, and the tj zone
# index is board-specific), check every one is readable, then loop. `cat` of a fixed file
# list is positional, so a silently-missing file would shift every field -- hence the
# `test -r` gate up front and the field-count assert in `parse` below.
PROBE = r"""
h=$(ls -d /sys/bus/i2c/drivers/ina3221*/*/hwmon/hwmon* 2>/dev/null | head -1)
tj=$(dirname $(grep -l tj-thermal /sys/devices/virtual/thermal/thermal_zone*/type | head -1))/temp
f="$h/in1_input $h/curr1_input $h/in2_input $h/curr2_input $h/in3_input $h/curr3_input"
f="$f $tj /sys/devices/platform/gpu.0/load"
for p in $f; do test -r "$p" || { echo "MISSING $p" >&2; exit 1; }; done
while :; do cat $f /proc/meminfo; echo .; sleep %.1f; done
"""
FIELDS = ("v1", "c1", "v2", "c2", "v3", "c3", "tj", "gpu")   # order of the cat above


def parse(block):
    """One `cat` block (list of lines, sentinel stripped) -> a reading dict.

    Rails are mV/mA, tj is milli-C, `gpu.0/load` is per-mille (0-1000, i.e. 999 = 99.9%
    busy -- NOT a percent, which is what makes it look plausible while reading 10x low).
    """
    nums, mem = block[:len(FIELDS)], block[len(FIELDS):]
    assert len(nums) == len(FIELDS), f"short block: {len(nums)} of {len(FIELDS)}"
    v = {k: int(n) for k, n in zip(FIELDS, nums)}
    kb = {}
    for line in mem:
        k, _, rest = line.partition(":")
        if k in ("MemTotal", "MemAvailable"):
            kb[k] = int(rest.split()[0])
    return {
        "vdd_in_w": v["v1"] * v["c1"] / 1e6,
        "cpu_gpu_cv_w": v["v2"] * v["c2"] / 1e6,
        "soc_w": v["v3"] * v["c3"] / 1e6,
        "tj_c": v["tj"] / 1000.0,
        "gpu_pct": v["gpu"] / 10.0,
        "ram_used_gb": (kb["MemTotal"] - kb["MemAvailable"]) / 1e6,
        "ram_total_gb": kb["MemTotal"] / 1e6,
        "t": time.time(),
    }


class OrinTelemetry:
    """One persistent ssh printing a sysfs block per second; `.last` is the newest.

    Failure is expected and cheap: the Orin reboots, the link drops, sshd restarts. The
    reader thread marks the reading stale, sleeps, and reconnects -- the panel shows a
    dash rather than a stale number, and nothing upstream has to care.
    """

    def __init__(self, host=HOST, period=PERIOD_S):
        self.host, self.period = host, period
        self.last, self.err = None, None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._proc, self._thread = None, None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        self._kill()

    def _kill(self):
        p, self._proc = self._proc, None
        if p is not None:
            try:
                p.kill()
            except OSError:
                pass

    def _run(self):
        while not self._stop.is_set():
            try:
                self._proc = subprocess.Popen(
                    ["ssh", "-T", "-q", self.host, PROBE % self.period],
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, text=True)
                block = []
                for line in self._proc.stdout:
                    line = line.strip()
                    if line != ".":
                        block.append(line)
                        continue
                    try:
                        with self._lock:
                            self.last, self.err = parse(block), None
                    except (AssertionError, ValueError, KeyError) as e:
                        with self._lock:
                            self.err = f"parse: {e}"
                    block = []
                    if self._stop.is_set():
                        break
                err = (self._proc.stderr.read() or "").strip() if self._proc else ""
            except OSError as e:
                err = str(e)
            self._kill()
            if self._stop.is_set():
                return
            with self._lock:
                self.last, self.err = None, err.splitlines()[-1] if err else "ssh closed"
            time.sleep(5.0)   # the Orin is down or busy rebooting: do not spin on it

    def read(self, max_age_s=5.0):
        """The newest reading if it is fresh, else None. Age, not liveness: a frozen
        `cat` loop keeps the ssh open, so 'the process is alive' is not the question."""
        with self._lock:
            r, e = self.last, self.err
        if r is None or time.time() - r["t"] > max_age_s:
            return None if r is None else dict(r, stale=True, err=e)
        return r


def demo():
    """Live check: the probe resolves on the device and the reading is plausible.
    The parser itself is covered offline in `tests/test_orin_telemetry.py`."""
    t = OrinTelemetry().start()
    for _ in range(6):
        time.sleep(1.0)
        print(t.read() or f"no reading yet ({t.err})")
    t.stop()


if __name__ == "__main__":
    demo()
