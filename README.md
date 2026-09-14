# python-logging-cost

What a log call costs across stdlib `logging`, structlog and loguru, and across
the three things you might ask them to do.

Measured **2026-09-14** on Apple M2, 8 GB, macOS 26.6.2 (arm64), CPython 3.14.7, 200,000 calls per configuration.

```
what you log        logging       structlog     loguru       spread
------------------------------------------------------------------------
below threshold     0.16          0.21          0.20         1.4x
plain text          5.81          6.25          7.49         1.3x
JSON output         5.66          5.13          16.49        3.2x

microseconds per call, 200,000 calls, minimum of five runs.
cheapest call 0.16 us, dearest 16.49 us: 105x.
```

Two findings. A call below the threshold costs about 0.2 microseconds in all
three, so guarding log calls in hot paths is solving a problem that does not
exist. And the libraries are within 1.4x of each other everywhere except JSON
output, where loguru's `serialize=True` is 3.2x slower than structlog's renderer
and 2.9x slower than a plain stdlib JSON formatter.

## Is loguru's JSON slow, or just verbose?

`serialize=True` emits 13 record fields and about 598 bytes per line. A structlog record
with four fields is about 100. Reporting "3.2x slower" without that compares two different
jobs, so loguru was run again through a custom sink emitting the same four fields:

```
loguru serialize=True   17.46 us/call   13 fields, 598 bytes
loguru four fields       9.49 us/call    4 fields, 100 bytes
structlog                5.13 us/call    4 fields, 100 bytes
```

About half the gap is verbosity. Matched field for field loguru is still 1.85x slower than
structlog, which is a real difference and a much smaller claim.

## Method

- Every library writes to an open file descriptor on `/dev/null`, so the disk is
  not in the measurement.
- 1,000 warm-up calls before timing, because all three build caches on first use.
- Five runs per configuration in fresh subprocesses; minimum reported.
- Each library is configured the way its own documentation shows for that mode.

## Limits

- One message shape, one field. Wider structured records will move the JSON row.
- `/dev/null` removes I/O contention, which a real sink would add.
- picologging was excluded: it has no wheel for CPython 3.14 and would not install.
- Absolute microseconds are laptop properties. The ratios should travel.

## Reproducing

```bash
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python bench/bench_logging.py
python3 bench/tables.py
```

MIT.
