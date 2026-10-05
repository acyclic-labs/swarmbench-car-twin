# The job: a twin of the car

(Draft. Final wording follows the decisions in the benchmark's DECISIONS.md.)

Write everything under `sim/`: an executable `sim/build` the grader runs once, an executable
`sim/run` it starts as `contract.json` says, and `sim/DECISION.md`. Started, the twin serves three
things on 127.0.0.1:

1. **The car's web API** on `--car-port`, over HTTPS with a self-signed certificate as on the car:
   exactly the routes, responses, login, CSRF and manual-drive mapping in `car/spec.json`
   `web_api`, so a client written for the real car works.
2. **A tracker** on `--tracker-port`: the car's pose as an overhead camera would report it, late
   by the `tracker` stage in `car/latency.json`.
3. **An admin port** on `--admin-port`: ground truth and an event log for the grader (schemas in
   `contract.json`).

## Parts (sizes add up: S includes XS, and so on)

| size | part | done when |
|---|---|---|
| XS | API, login, CSRF, mapping, modes, start/stop, no watchdog | `api`, `mapping`, `control` checks pass |
| S | latency per stage from `--latency` and `--wan`; tracker | `latency`, `tracker` checks pass |
| M | physics (`car/spec.json` vehicle), MJPEG camera, steady 200 Hz loop while streaming | `physics`, `camera`, `realtime` checks pass |
| L | `--watchdog-ms`, `--cars N`, latency measurement tool | `watchdog`, `fleet`, `measure` checks pass |

## Your choices

The language, libraries, physics and rendering approach and process layout are yours. The twin
has to hold a steady physics loop while serving HTTPS clients, streaming video and delaying every
stage on time, so the choice matters. Record it in `sim/DECISION.md`: what you chose, what you
considered, what you measured or tried before committing, the risks, and what would change your
mind. `sim/build` has 15 minutes.

**Today the choice is limited** by the box your agents work in: Python 3.11 standard library, no
package downloads, no compilers. See "Where your code runs" in `README.md`; it overrides this file.

Values marked `estimate` in the car files are still the values to reproduce.
