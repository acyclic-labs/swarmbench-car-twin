"""Public XS checks: login, CSRF and the manual-drive mapping, as the real car does them."""
import json

from check import check


@check("api", "page-has-csrf-meta")
def _(ctx):
    ctx.session(login=False)  # asserts the meta tag


@check("api", "api-needs-login")
def _(ctx):
    s = ctx.session(login=False)
    status, _, _ = s.call("GET", "/api/get_battery_level")
    assert status == 401, f"GET /api/get_battery_level without login returned {status}, want 401"


@check("api", "put-needs-csrf")
def _(ctx):
    s = ctx.session()
    status, _, _ = s.call("PUT", "/api/start_stop", {"start_stop": "stop"}, csrf=False)
    assert status == 400, f"PUT without X-CSRFToken returned {status}, want 400"


@check("api", "wrong-password-fails")
def _(ctx):
    s = ctx.session(login=False)
    status, _, body = s.call("POST", "/login", "password=not-it",
                             {"Content-Type": "application/x-www-form-urlencoded"})
    assert s.cookie("deepracer_token") is None, "a wrong password set deepracer_token"


@check("mapping", "rescale-examples")
def _(ctx):
    s = ctx.session()
    s.json("PUT", "/api/drive_mode", {"drive_mode": "manual"})
    s.json("PUT", "/api/start_stop", {"start_stop": "start"})
    for throttle, max_speed, want in [(0.3, 0.1, 0.1383742911153119), (0.8, 1.0, 0.992)]:
        s.json("PUT", "/api/manual_drive", {"angle": 0.0, "throttle": throttle, "max_speed": max_speed})
        got = ctx.state()["throttle_cmd"]
        assert abs(got - (-want)) < 1e-9, f"throttle {throttle} max_speed {max_speed}: msg.throttle {got}, want {-want}"
    s.json("PUT", "/api/start_stop", {"start_stop": "stop"})
