"""Is loguru's JSON slow, or is it just verbose?

serialize=True emits 13 record fields and about 598 bytes per line, against the
100 bytes of a four-field structlog record. Reporting "3.2x slower" without that
is comparing two different jobs. This adds a loguru configuration that emits the
same four fields, so the library cost can be separated from the payload cost.
"""
from __future__ import annotations
import json, pathlib, statistics, subprocess

ROOT = pathlib.Path(__file__).resolve().parent
PY = str(ROOT / ".venv" / "bin" / "python")
REPS, N = 5, 200_000

SRC = r'''
import json, sys, time
MODE, N = sys.argv[1], int(sys.argv[2])
sink = open("/dev/null", "w")
from loguru import logger
logger.remove()
if MODE == "default":
    logger.add(sink, serialize=True, level="INFO")
else:
    # same four fields structlog emits: level, timestamp, event, user
    def minimal(rec):
        r = rec["record"]
        return json.dumps({"level": r["level"].name,
                           "timestamp": r["time"].isoformat(),
                           "event": r["message"],
                           "user": r["extra"].get("user")})
    logger.add(lambda m: sink.write(minimal(m.record and {"record": m.record}) + "\n"),
               level="INFO")
emit = lambda i: logger.bind(user=i).info("request served")
for i in range(1000): emit(i)
t0 = time.perf_counter()
for i in range(N): emit(i)
print(json.dumps({"ms": (time.perf_counter() - t0) * 1000}))
'''

def once(mode):
    p = subprocess.run([PY, "-c", SRC, mode, str(N)], capture_output=True, text=True, timeout=900)
    if p.returncode != 0:
        return None, (p.stderr or "").strip().splitlines()[-1][:200]
    return json.loads(p.stdout.strip().splitlines()[-1])["ms"], None

rows = []
for mode in ("default", "minimal"):
    once(mode)
    s, err = [], None
    for _ in range(REPS):
        ms, err = once(mode)
        if ms is None: break
        s.append(ms)
    if not s:
        print(f"  loguru {mode}: FAILED {err}"); rows.append({"mode": mode, "error": err}); continue
    rows.append({"mode": mode, "min_ms": round(min(s),1), "per_call_us": round(min(s)*1000/N,3)})
    print(f"  loguru {mode:9} {min(s):8.1f} ms  {min(s)*1000/N:7.3f} us/call")

(ROOT/"results"/"logging_fair.json").write_text(json.dumps(
    {"n": N, "reps": REPS, "rows": rows,
     "payload_bytes": {"loguru_default": 598, "structlog": 100}}, indent=2))
print("\nwrote results/logging_fair.json")
