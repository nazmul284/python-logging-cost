"""What does a log line cost, across the libraries people actually choose?

Three configurations per library, because the cost is dominated by what you ask
for rather than which library you picked:
  discarded - level below threshold. The call that "does nothing".
  plain     - a formatted line to a null stream.
  json      - structured output, which is what production actually runs.

Everything writes to an open file descriptor on /dev/null so the measurement is
the library, not the disk.
"""
from __future__ import annotations
import json, pathlib, statistics, subprocess

ROOT = pathlib.Path(__file__).resolve().parent
PY = str(ROOT / ".venv" / "bin" / "python")
REPS, N = 5, 200_000

SRC = r'''
import json, logging, sys, time, io
LIB, MODE, N = sys.argv[1], sys.argv[2], int(sys.argv[3])
sink = open("/dev/null", "w")

if LIB == "stdlib":
    lg = logging.getLogger("b"); lg.propagate = False
    h = logging.StreamHandler(sink)
    if MODE == "json":
        class JF(logging.Formatter):
            def format(self, r):
                return json.dumps({"lvl": r.levelname, "msg": r.getMessage(),
                                   "t": r.created, "user": getattr(r, "user", None)})
        h.setFormatter(JF())
    else:
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    lg.addHandler(h)
    lg.setLevel(logging.WARNING if MODE == "discarded" else logging.INFO)
    emit = lambda i: lg.info("request served", extra={"user": i})

elif LIB == "structlog":
    import structlog
    procs = [structlog.processors.add_log_level, structlog.processors.TimeStamper(fmt="iso")]
    procs.append(structlog.processors.JSONRenderer() if MODE == "json"
                 else structlog.dev.ConsoleRenderer(colors=False))
    structlog.configure(processors=procs,
        wrapper_class=structlog.make_filtering_bound_logger(
            30 if MODE == "discarded" else 20),
        logger_factory=structlog.PrintLoggerFactory(file=sink), cache_logger_on_first_use=True)
    lg = structlog.get_logger()
    emit = lambda i: lg.info("request served", user=i)

else:  # loguru
    from loguru import logger
    logger.remove()
    if MODE == "json":
        logger.add(sink, serialize=True, level="WARNING" if MODE == "discarded" else "INFO")
    else:
        logger.add(sink, level="WARNING" if MODE == "discarded" else "INFO")
    if MODE == "discarded":
        logger.remove(); logger.add(sink, level="WARNING")
    emit = lambda i: logger.info("request served user={}", i)

for i in range(1000):        # warm: first call builds caches in every library
    emit(i)
t0 = time.perf_counter()
for i in range(N):
    emit(i)
el = (time.perf_counter() - t0) * 1000
sink.flush()
print(json.dumps({"ms": el}))
'''

def once(lib, mode):
    p = subprocess.run([PY, "-c", SRC, lib, mode, str(N)],
                       capture_output=True, text=True, timeout=900)
    if p.returncode != 0:
        return None, (p.stderr or "").strip().splitlines()[-1][:160]
    return json.loads(p.stdout.strip().splitlines()[-1])["ms"], None

rows = []
for mode in ("discarded", "plain", "json"):
    for lib in ("stdlib", "structlog", "loguru"):
        once(lib, mode)
        s, err = [], None
        for _ in range(REPS):
            ms, err = once(lib, mode)
            if ms is None: break
            s.append(ms)
        if not s:
            rows.append({"mode": mode, "lib": lib, "error": err})
            print(f"  {mode:10} {lib:10} FAILED {err}"); continue
        rows.append({"mode": mode, "lib": lib, "n": N,
                     "min_ms": round(min(s), 1),
                     "per_call_us": round(min(s) * 1000 / N, 3), "error": None})
        print(f"  {mode:10} {lib:10} {min(s):9.1f} ms  "
              f"{min(s)*1000/N:8.3f} us/call", flush=True)

(ROOT/"results"/"logging.json").write_text(json.dumps({"reps": REPS, "n": N, "rows": rows}, indent=2))
print("\nwrote results/logging.json")
