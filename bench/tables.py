"""Render the article/README tables from the result JSON."""
from __future__ import annotations
import json, pathlib
R = pathlib.Path(__file__).resolve().parent.parent / "results"
D = json.loads((R / "logging.json").read_text())
L = {(r["mode"], r["lib"]): r for r in D["rows"]}
MODES = [("discarded","below threshold"),("plain","plain text"),("json","JSON output")]
LIBS = ["stdlib","structlog","loguru"]

def row(c, w): return "".join(str(x).ljust(n) for x, n in zip(c, w)).rstrip()
def rule(w):   return "-" * sum(w)

def costs() -> str:
    w = [20, 14, 14, 13, 11]
    out = [row(["what you log","logging","structlog","loguru","spread"], w), rule(w)]
    for m, lab in MODES:
        v = [L[(m,l)]["per_call_us"] for l in LIBS]
        out.append(row([lab] + [f"{x:.2f}" for x in v] + [f"{max(v)/min(v):.1f}x"], w))
    lo = min(L[("discarded",l)]["per_call_us"] for l in LIBS)
    hi = max(L[("json",l)]["per_call_us"] for l in LIBS)
    out += ["", f"microseconds per call, 200,000 calls, minimum of five runs.",
            f"cheapest call {lo:.2f} us, dearest {hi:.2f} us: {hi/lo:.0f}x."]
    return "\n".join(out)

if __name__ == "__main__":
    print("===== COST PER CALL =====\n" + costs())
