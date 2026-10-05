"""Public S check: the tracker refreshes at the rate in car/timing.json."""
import json
import time

from check import check


@check("tracker", "rate", sizes="S")
def _(ctx):
    tr, seqs, end = ctx.car_json("timing.json")["twin"]["tracker"], set(), time.perf_counter() + 3.0
    while time.perf_counter() < end:
        status, _, body = ctx.get(ctx.tracker, "/pose")
        assert status == 200, f"/pose returned {status}"
        seqs.add(json.loads(body)["seq"])
    hz = (len(seqs) - 1) / 3.0
    lo, hi = tr["hz"] * (1 - tr["hz_tolerance"]), tr["hz"] * (1 + tr["hz_tolerance"])
    assert lo <= hz <= hi, f"tracker refreshed at {hz:.1f} Hz, want {lo:.1f}-{hi:.1f}"
