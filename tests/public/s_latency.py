"""Public S checks: request latency matches car/latency.json (thresholds: car/timing.json twin)."""
from check import check, quantile, timed, within


@check("latency", "battery-rtt", sizes="S")
def _(ctx):
    """GET /api/get_battery_level: two Wi-Fi legs + nginx/Flask + a ROS service call."""
    tw, s = ctx.car_json("timing.json")["twin"], ctx.session()
    got = timed(lambda: s.json("GET", "/api/get_battery_level"), tw["probes"])
    want = ctx.expected_ms(["wifi_one_way", "wifi_one_way", "onboard_api", "onboard_service_call"])
    band = tw["latency_band"]
    within("p50", quantile(got, 0.5), quantile(want, 0.5), band["p50"], band["floor_ms"])
    within("p99", quantile(got, 0.99), quantile(want, 0.99), band["p99"], band["floor_ms"])
