"""Device-vs-simulation parity for `dam4sam_lt` over the 33 night sequences.

The claim under test: the LT wrapper is open-loop, so replaying the recorded (box, conf) trace of
`dam4sam_t640` through `run_machine_rel` must reproduce the arm exactly. Verified on `car2` alone
(0/1321); 33 sequences turns that into evidence.
"""
import json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, "analysis")
from lt_sim import run_machine_rel

REAL, SIM = Path("raw/night-damlt"), Path("raw/dam-conf33")
tot = dif = boxdif = nseq = 0
bad = []
for p in sorted(REAL.glob("dam4sam_lt__*.json")):
    seq = json.loads(p.read_text())["meta"]["seq"]
    q = SIM / f"dam4sam_t640__{seq}.json"
    if not q.exists():
        print(f"no base trace for {seq}"); continue
    r = {x["i"]: x for x in json.loads(p.read_text())["rows"]}
    b = {x["i"]: x for x in json.loads(q.read_text())["rows"]}
    n = max(max(r), max(b)) + 1
    conf = np.array([b.get(i, {}).get("conf", None) or np.nan for i in range(n)], float)
    want = run_machine_rel(conf, 4.0, 2.0, 1, 300, False) & np.array(
        [b.get(i, {}).get("box") is not None for i in range(n)])
    got = np.array([r.get(i, {}).get("box") is not None for i in range(n)])
    d = int((want != got).sum())
    # when both answer, the box must be the base tracker's box: the wrapper never alters it
    bd = sum(1 for i in range(n) if want[i] and got[i] and r[i]["box"] != b[i]["box"])
    tot += n; dif += d; boxdif += bd; nseq += 1
    if d or bd:
        bad.append(f"  {seq:14s} {n:5d} fr  mascara {d:4d}  caja {bd:4d}")
print(f"{nseq} secuencias, {tot} frames: {dif} frames de mascara distintos, {boxdif} cajas distintas")
print("\n".join(bad) if bad else "  paridad exacta")
