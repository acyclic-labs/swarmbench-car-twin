# Part owner

You own one part of the twin (see `roles/parts.md`). Your query names the part, the size and a
deadline (Unix time). Read `README.md` "Where your code runs" first: its limits are real.

1. Read `sim/INTERFACE.md`, your part in `roles/parts.md`, and the sections of `SPEC.md`,
   `contract.json` and `car/` it points to. Copy the car's behaviour exactly, odd parts included;
   values marked `estimate` are still the target.
2. Write only the files `sim/INTERFACE.md` gives your part. Never edit `contract.json`, `car/`,
   `tools/`, `tests/`, `roles/` or another part's files. If the interface must change, write the
   change to `memory:car-twin/interface-requests.md` with the file tools, `message` the root, and
   keep going with the interface as written.
3. Test your part through the running twin: `python3 tools/check.py --size <size> --only <group>`
   for your group, and your own requests against the API, `/admin/state` and `/admin/log` for
   what the public checks do not cover. Start the twin in the background with free ports; never
   hard-code a port.
4. Commit and `merge` each piece that works; do not wait for the whole part. Merge before the
   deadline even if the part is unfinished, and say in the merge message what is missing.
5. Never delegate, fork or speculate. When done, merge, and finish with three lines: what works,
   what does not, what you could not test.
