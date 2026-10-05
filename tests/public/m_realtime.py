"""Public M check: the physics loop holds its rate while two camera streams are open."""
import json
import statistics
import threading
import time

from check import check, quantile


@check("realtime", "ticks-under-camera-load", sizes="M")
def _(ctx):
    ph, cam = (ctx.car_json("timing.json")["twin"][k] for k in ("physics", "camera"))
    streams = [threading.Thread(target=ctx.session().stream, args=(6.0,), daemon=True)
               for _ in range(cam["streams_open_during_realtime"])]
    [t.start() for t in streams]
    time.sleep(4.0)
    status, _, body = ctx.get(ctx.admin, "/admin/ticks")
    [t.join() for t in streams]
    assert status == 200, f"/admin/ticks returned {status}"
    d = json.loads(body)
    iv, nominal = d["intervals_ms"], 1000 / d["hz"]
    assert len(iv) >= 1000, f"only {len(iv)} tick intervals reported (want >= 1000)"
    hz = 1000 / statistics.mean(iv)
    assert d["hz"] >= ph["min_hz"] and hz >= ph["min_hz"] * 0.99, f"physics at {hz:.1f} Hz (nominal {d['hz']}), want >= {ph['min_hz']}"
    jitter = quantile([abs(x - nominal) for x in iv], 0.99)
    assert jitter <= ph["max_tick_jitter_p99_ms"], f"tick jitter p99 {jitter:.2f} ms > {ph['max_tick_jitter_p99_ms']} ms"
