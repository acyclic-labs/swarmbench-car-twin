"""Run conformance checks against a DeepRacer twin started per contract.json.

    python3 tools/check.py                    # build sim/, start sim/run, run the public checks
    python3 tools/check.py --size S --only api
    python3 tools/check.py --url http://host:port --no-start   # an already running twin (or car)

A check is a function registered with @check(group, id, sizes): it gets a Ctx and raises
AssertionError (fail) or returns normally (pass). Prints one JSON object. The grader runs the same
runner with its own, larger set of checks. Never edit this file.
"""
import argparse
import glob
import http.cookiejar
import importlib.util
import json
import math
import os
import random
import re
import socket
import ssl
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SIZES = ["XS", "S", "M", "L"]
CHECKS = []
# The car serves HTTPS with a self-signed certificate and its clients do not verify it.
TLS = ssl.create_default_context()
TLS.check_hostname, TLS.verify_mode = False, ssl.CERT_NONE


def check(group, id, sizes="XS"):
    """Register a check that applies from size `sizes` upward."""
    def reg(fn):
        CHECKS.append({"group": group, "id": id, "from": sizes, "fn": fn})
        return fn
    return reg


class Ctx:
    def __init__(self, car, tracker, admin, password, seed, latency, wan, size):
        self.car, self.tracker, self.admin = car, tracker, admin
        self.password, self.seed, self.latency, self.wan, self.size = password, seed, latency, wan, size

    def get(self, base, path, headers=None, timeout=10):
        return _req("GET", base + path, None, headers, timeout)

    def send(self, base, path, body=None, method="PUT", headers=None, timeout=10):
        return _req(method, base + path, body, headers, timeout)

    def session(self, login=True):
        """A cookie-keeping client that has read the CSRF token and (by default) logged in."""
        s = Session(self.car)
        if login:
            s.login(self.password)
        return s

    def car_json(self, name):
        """A file from car/ (spec.json, latency.json, timing.json)."""
        return json.load(open(os.path.join(os.path.dirname(self.latency), name)))

    def expected_ms(self, stages, n=20000, seed=1):
        """Samples (ms) of the sum of latency.json stages; 'wifi_one_way' etc. by name,
        'pwm_frame' = uniform wait for the next servo frame, ('uniform', hi_ms) for a hold."""
        lat, spec, rng = self.car_json("latency.json"), self.car_json("spec.json"), random.Random(seed)
        out = []
        for _ in range(n):
            ms = 0.0
            for st in stages:
                if isinstance(st, tuple):
                    ms += rng.uniform(0, st[1])
                elif st == "pwm_frame":
                    ms += rng.uniform(0, 1000 / spec["vehicle"]["servo_pwm_hz"]["value"])
                else:
                    d = lat["stages"][st]
                    sigma = math.log(d["p99_ms"] / d["median_ms"]) / 2.326
                    ms += rng.lognormvariate(math.log(d["median_ms"]), sigma)
                    ms += lat["rto_ms"] if rng.random() < d.get("loss", 0) else 0
            out.append(ms)
        return out

    def state(self):
        status, _, body = self.get(self.admin, "/admin/state")
        assert status == 200, f"/admin/state returned {status}"
        return json.loads(body)


class Session:
    """What the real car's clients do: GET / for the csrf-token meta, then POST /login."""

    def __init__(self, base):
        self.base, self.jar = base, http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar),
                                                  urllib.request.HTTPSHandler(context=TLS))
        status, _, page = self.call("GET", "/")
        m = re.search(rb'<meta[^>]+name="csrf-token"[^>]+content="([^"]+)"', page)
        assert m, f"GET / ({status}) has no <meta name=\"csrf-token\">"
        self.csrf = m.group(1).decode()

    def login(self, password):
        status, _, body = self.call("POST", "/login", urllib.parse.urlencode({"password": password}),
                                    {"Content-Type": "application/x-www-form-urlencoded"})
        assert status == 200 and self.cookie("deepracer_token"), f"login failed: {status} {body[:200]!r}"

    def cookie(self, name):
        return next((c.value for c in self.jar if c.name == name), None)

    def call(self, method, path, body=None, headers=None, csrf=True, timeout=10):
        headers = dict(headers or {})
        if csrf and method != "GET" and getattr(self, "csrf", None):
            headers["X-CSRFToken"] = self.csrf
        return _req(method, self.base + path, body, headers, timeout, self.opener)

    def stream(self, seconds, topic="/camera_pkg/display_mjpeg"):
        """Read the MJPEG stream for `seconds`; returns the arrival times (s) of each JPEG start."""
        r = urllib.request.Request(f"{self.base}/route?topic={topic}&width=480&height=360")
        arrivals, tail, end = [], b"", time.perf_counter() + seconds
        with self.opener.open(r, timeout=5) as resp:
            while time.perf_counter() < end:
                chunk = resp.read1(65536) if hasattr(resp, "read1") else resp.read(4096)
                if not chunk:
                    break
                buf = tail + chunk
                arrivals += [time.perf_counter()] * buf.count(b"\xff\xd8\xff")
                tail = buf[-2:]
        return arrivals

    def json(self, method, path, body=None, **kw):
        status, _, raw = self.call(method, path, body, **kw)
        assert status == 200, f"{method} {path} returned {status}: {raw[:200]!r}"
        return json.loads(raw)


def _req(method, url, body, headers, timeout, opener=None):
    """(status, headers, bytes). JSON bodies for dict, raw for bytes/str."""
    data = None
    headers = dict(headers or {})
    if isinstance(body, dict):
        data = json.dumps(body).encode()
        headers.setdefault("Content-Type", "application/json")
    elif body is not None:
        data = body.encode() if isinstance(body, str) else body
    r = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with (opener or urllib.request.build_opener(urllib.request.HTTPSHandler(context=TLS))).open(
                r, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def quantile(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * q))]


def within(name, got, want, band, floor_ms):
    """Assert got is want +/- band (fraction), widened by floor_ms."""
    lo, hi = want * (1 - band) - floor_ms, want * (1 + band) + floor_ms
    assert lo <= got <= hi, f"{name}: {got:.1f} ms, want {want:.1f} ms (band {lo:.1f}-{hi:.1f})"


def timed(fn, n):
    """Run fn n times; latencies in ms."""
    out = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t0) * 1000)
    return out


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def load(dirs):
    for d in dirs:
        for path in sorted(glob.glob(os.path.join(d, "*.py"))):
            spec = importlib.util.spec_from_file_location(f"checks_{os.path.basename(path)[:-3]}", path)
            spec.loader.exec_module(importlib.util.module_from_spec(spec))


def build(contract, workdir):
    """Run the twin's build step once; (seconds, log tail)."""
    b = contract["build"]
    t0 = time.time()
    try:
        r = subprocess.run(b["cmd"], cwd=workdir, capture_output=True, text=True, timeout=b["within_s"])
    except FileNotFoundError:
        raise RuntimeError(f"no build step: {b['cmd'][0]} is missing or not executable")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"build took longer than {b['within_s']} s")
    if r.returncode:
        raise RuntimeError(f"build failed ({r.returncode}): {(r.stdout + r.stderr)[-2000:]}")
    return round(time.time() - t0, 1)


def stack(workdir):
    """What the twin is made of, recorded for later analysis of the swarm's choice (not scored)."""
    sim, exts, lines = os.path.join(workdir, "sim"), {}, 0
    manifests = ("Cargo.toml", "go.mod", "CMakeLists.txt", "package.json", "pyproject.toml",
                 "requirements.txt", "Dockerfile", "build.zig", "Makefile")
    found = []
    for dp, dns, fs in os.walk(sim):
        dns[:] = [d for d in dns if d not in ("target", "node_modules", ".git", "build", "__pycache__", "vendor")]
        for f in fs:
            if f in manifests:
                found.append(os.path.relpath(os.path.join(dp, f), sim))
            ext = os.path.splitext(f)[1]
            if not ext:  # an extensionless script such as sim/run: name it by its interpreter
                try:
                    first = open(os.path.join(dp, f), "rb").readline()
                except OSError:
                    first = b""
                ext = {b"python": ".py", b"node": ".js", b"sh": ".sh", b"bash": ".sh"}.get(
                    next((k for k in (b"python", b"node", b"bash", b"sh") if first.startswith(b"#!") and k in first), None), "")
            if ext in (".rs", ".go", ".c", ".cc", ".cpp", ".h", ".hpp", ".py", ".js", ".ts", ".zig", ".java", ".kt", ".sh"):
                try:
                    n = sum(1 for _ in open(os.path.join(dp, f), errors="replace"))
                except OSError:
                    continue
                exts[ext] = exts.get(ext, 0) + n
                lines += n
    record = os.path.join(sim, "DECISION.md")
    return {"lines_by_ext": dict(sorted(exts.items(), key=lambda kv: -kv[1])), "lines": lines,
            "manifests": sorted(found), "decision_record": os.path.isfile(record),
            "decision_record_bytes": os.path.getsize(record) if os.path.isfile(record) else 0}


def start(contract, workdir, fill, size):
    cmd = [c.format(**fill) for c in contract["start"]]
    cmd += [c.format(**fill) for c in contract.get("flags_from_size", {}).get(size, [])]
    proc = subprocess.Popen(cmd, cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    ready = contract["ready"]
    url, deadline = ready["url"].format(**fill), time.time() + ready["within_s"]
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"twin exited with {proc.returncode}: {proc.stdout.read()[-2000:]}")
        try:
            if _req("GET", url, None, None, 2)[0] == ready["status"]:
                return proc
        except OSError:
            pass
        time.sleep(0.2)
    proc.kill()
    raise RuntimeError(f"twin not ready at {url} within {ready['within_s']} s")


def run(dirs, workdir, size="XS", only=None, url=None, seed=20261004, wan="none"):
    sys.modules.setdefault("check", sys.modules[__name__])  # check files do `from check import check`
    load(dirs)
    contract = json.load(open(os.path.join(workdir, "contract.json")))
    selected = [c for c in CHECKS if SIZES.index(c["from"]) <= SIZES.index(size)
                and (not only or c["group"] in only)]
    fill = {"car_port": free_port(), "tracker_port": free_port(), "admin_port": free_port(), "seed": seed,
            "latency": os.path.join(workdir, "car", "latency.json"), "wan": wan,
            "password": "twin-check", "watchdog_ms": 300, "cars": 2}
    proc, out = None, {"size": size, "checks": [], "error": None, "build_s": None, "stack": None}
    try:
        if url:
            car, tracker, admin = url.rstrip("/"), None, None
        else:
            out["stack"] = stack(workdir)
            out["build_s"] = build(contract, workdir)
            proc = start(contract, workdir, fill, size)
            car = contract["car"]["base"].format(**fill)
            tracker, admin = f"http://127.0.0.1:{fill['tracker_port']}", f"http://127.0.0.1:{fill['admin_port']}"
        ctx = Ctx(car, tracker, admin, fill["password"], seed, fill["latency"], wan, size)
        for c in selected:
            t0, res = time.time(), {"group": c["group"], "id": c["id"]}
            try:
                c["fn"](ctx)
                res["ok"] = True
            except AssertionError as e:
                res["ok"], res["why"] = False, str(e)[:500]
            except Exception as e:  # a crash in the twin or the check counts as a failure
                res["ok"], res["why"] = False, f"{type(e).__name__}: {e}"[:500]
                res["trace"] = traceback.format_exc(limit=3)[-800:]
            res["s"] = round(time.time() - t0, 3)
            out["checks"].append(res)
    except Exception as e:
        out["error"] = str(e)[:2000]
    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                proc.kill()
    passed = sum(c["ok"] for c in out["checks"])
    out.update(passed=passed, total=len(selected),
               groups={g: [sum(c["ok"] for c in out["checks"] if c["group"] == g),
                           sum(1 for c in selected if c["group"] == g)]
                       for g in sorted({c["group"] for c in selected})})
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--size", default="XS", choices=SIZES)
    p.add_argument("--only", action="append", help="check group (repeatable)")
    p.add_argument("--url", help="test an already running car API instead of building and starting sim/")
    p.add_argument("--no-start", action="store_true")
    p.add_argument("--checks", action="append", help="check directory (default tests/public)")
    p.add_argument("--workdir", default=ROOT)
    a = p.parse_args()
    out = run(a.checks or [os.path.join(ROOT, "tests", "public")], a.workdir, a.size, a.only,
              a.url if a.no_start or a.url else None)
    for c in out["checks"]:
        if not c["ok"]:
            print(f"FAIL {c['group']}/{c['id']}: {c['why']}", file=sys.stderr)
    print(json.dumps({k: v for k, v in out.items() if k != "checks"} | {"failed": [
        f"{c['group']}/{c['id']}" for c in out["checks"] if not c["ok"]]}, indent=1))
    sys.exit(0 if not out["error"] and out["passed"] == out["total"] else 1)


if __name__ == "__main__":
    main()
