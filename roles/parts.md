# The parts of the twin

How the twin splits between agents. Sizes add up: S includes XS. Every fact you need is in
`SPEC.md`, `contract.json` and `car/`; this file only says which of it each part owns. The root
writes `sim/INTERFACE.md` before any part starts: which files each part owns and the calls between
parts. Follow it; if it is wrong, say so to the root rather than editing another part's files.

## api (XS)
The car's web API on `--car-port`, over HTTPS with a self-signed certificate.
- `car/spec.json` `web_api`: `transport`, `auth`, `csrf`, `routes`. `GET /` with the CSRF meta
  tag, `POST /login`, the session cookie, login required on `/api/*`, the CSRF header on every
  POST and PUT, every route with the car's response shapes, including `success: false` with HTTP
  200 on bad input.
- Writes one `request` event per request to the admin log (`contract.json` `admin.events.request`).
- Hands each accepted command to the control part through the interface; never decides what a
  command does to the car.
- Public checks: group `api`.

## control (XS)
What the car does with a command, and the admin port.
- `car/spec.json` `web_api.manual_drive_mapping` and `signs`, `onboard` (`watchdog`,
  `stop_behaviour`, `boot_state`, `battery_levels`): the rounding, rescale and sign inversion of
  manual drive, drive modes, start and stop, no watchdog, battery.
- The admin port on `--admin-port` (`contract.json` `admin`): `/admin/ready`, `/admin/state`,
  `/admin/log`, `/admin/reset`, and the `applied` events.
- Public checks: group `mapping`. There is no public `control` check: test start, stop and the
  missing watchdog yourself through the API and `/admin/state`.

## latency (S)
Time, as the real car spends it.
- `car/latency.json` from `--latency`, the `--wan` profile: every stage, the loss and
  retransmit rule, the cost of a new connection; `car/timing.json` `twin` for the tolerances.
- Each request is delayed where the car spends the time (network legs, the onboard handler,
  service calls); each command reaches the servo after the onboard delays and the wait for the
  next servo frame, and its `applied` event carries that time and its `request_seq`.
- One clock for everything (`contract.json` `clock`). Delaying one request must never delay
  another.
- Public checks: group `latency`.

## tracker (S)
The overhead camera's view of the car on `--tracker-port`.
- `contract.json` `tracker`: `GET /pose` with `t`, `seq`, `x`, `y`, `yaw`, `v`, refreshed at the
  rate in `car/timing.json` `twin.tracker`, each pose served late by the `tracker` stage.
- The pose comes from the vehicle state. Physics arrives at M: until then the car may hold still,
  but `t`, `seq`, the rate and the age must already be right, on the same clock as the admin port.
- Public checks: group `tracker`.
