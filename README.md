# car-twin starter

Build a digital twin of the car described in `car/spec.json` (an AWS DeepRacer): a program in
`sim/` that its real clients can drive unchanged, with the latency in `car/latency.json`.

| path | what | edit? |
|---|---|---|
| `SPEC.md` | the job, part by part | no |
| `contract.json` | how the grader starts your twin and the admin/tracker endpoints it reads | no |
| `car/spec.json` | the real car's API and behaviour, each fact with its source | no |
| `car/latency.json` | latency per stage to reproduce | no |
| `car/timing.json` | the thresholds the timing checks use | no |
| `tools/check.py` | runs the checks: `python3 tools/check.py --size XS` | no |
| `tests/public/` | about a fifth of the grader's checks | no |
| `roles/` | briefs for the agents of a swarm (part owner, reviewer) and the parts | no |
| `sim/` | **your twin**: `sim/build` (run once), `sim/run` (entry point), `sim/DECISION.md` | yes: everything you write goes here |

Language, libraries and architecture are yours to choose within the limits below. Write down why
in `sim/DECISION.md` (sections in `contract.json`). The grader copies only `sim/` from your run,
builds it on a clean Linux x86_64 box and uses its own copies of everything else.

## Where your code runs (read before choosing a stack)

These are the limits of the box every agent works in today. They override anything in
`SPEC.md` or `contract.json` that suggests otherwise (for example "`sim/build` may fetch
dependencies").

1. **Python 3.11 standard library only.** There is no pip and no compiler (no gcc, Go, Rust,
   Node or Java), and the network blocks every package registry (PyPI, npm, crates.io, the Go
   proxy, Debian mirrors). `make`, `git`, `curl` and the `openssl` command exist; github.com is
   reachable. `sim/build` must therefore work offline with what the box has. Python's `ssl` can
   serve a certificate but cannot create one: use the `openssl` command for the self-signed one.
2. **Small machine.** About 3 GB of disk and a few GiB of memory. `nproc` reports 48 or more, but
   that is the shared host, not your share: never size thread or process pools from it. Keep the
   running twin under 512 MB.
3. **Keep the workspace small.** Everything in the workspace is copied to every agent and to the
   grader. Build output, certificates, caches and logs go under `/tmp` (or a `mktemp -d`
   directory), never into the workspace; create them in `sim/build` or when `sim/run` starts.
   Never commit a file over 1 MB.
4. **One shell call returns after at most 10 minutes** (`timed_out: true`). Start servers and long
   jobs in the background (`nohup … > /tmp/x.log 2>&1 &`) and poll them with short calls. A
   background process keeps running between your shell calls. Pipe long output to a file and
   `tail` it.
5. **Every agent is stopped at 60 minutes**, and the whole swarm stops at its budget. Commit and
   merge working pieces as you go; leave time at the end.
6. **Agents do not share a machine.** A delegated agent starts in a fresh box with only the
   workspace files: no `/tmp`, no running processes, nothing built. Each agent builds and starts
   its own twin to test it. Never hard-code ports: take them from `sim/run`'s flags, and let
   `tools/check.py` pick free ones.
7. **Other agents see your files only after you merge.** To agree on something while you all
   work (an interface, a field name, a clock), write a note under `memory:car-twin/` with the file
   tools (`acyclic.filesystem`, `acyclic.edit`). The shell cannot read `memory:` paths, so copy
   what you need into your code. Notes are small, and the last writer wins: one writer per note.
8. **Turn off Nagle.** Set `TCP_NODELAY` on every socket your servers accept. Without it Linux adds
   about 40 ms to responses on a kept-alive connection, which ruins every latency figure.
9. **Timing measured in this box is indicative only.** The box can stall for up to 17 ms. The
   grader runs the timing checks (latency, tracker, real time) on a fixed, dedicated Linux
   x86_64 machine. If a public timing check fails narrowly here, check your model against
   `car/latency.json` and `car/timing.json` before tuning to the noise.
10. **`sim/build` and `sim/run` must be executable**: `chmod +x sim/build sim/run` and commit the
    mode (`git add --chmod=+x sim/build sim/run`).
11. **The public checks are a sample.** `tests/public/` does not cover every group (at XS there is
    no public `control` check); `--only <group>` with no public check in that group runs nothing
    and proves nothing. Test the rest against `SPEC.md` and `car/spec.json` yourself, through
    the API and `/admin/state` and `/admin/log`.
