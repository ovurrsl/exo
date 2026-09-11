# A2 — `feat/nic-link-speed`

Compare: https://github.com/exo-explore/exo/compare/main...ovurrsl:exo:feat/nic-link-speed?expand=1

Open this one **last**. It is the largest of the six and one half of it cannot
be verified without a Mac. If a maintainer asks to split it, the natural cut is
to keep `active_speed_mbps` and drop `supported_speed_mbps` into a follow-up —
that is said explicitly in the description below so the offer is already on the
table.

## Title

```
feat(profiling): report negotiated and supported link speed per interface
```

## Description

```markdown
## Motivation

`NetworkInterfaceInfo` carries an interface's name, address and type, but not
how fast the link actually is. Placement and the dashboard therefore cannot
distinguish a 10 GbE link from a 1 GbE one, or tell a user that a node fell back
to a slow link — which in a cluster whose throughput is bounded by the
interconnect is the number that explains a slow run.

Two different numbers are useful and they are not the same thing: the speed the
link negotiated right now, and the fastest the hardware could negotiate. A node
sitting at 1 Gb on a 10 Gb card is a cabling problem, and only the pair of
numbers makes that visible.

## Changes

- `src/exo/shared/types/profiling.py`: two optional fields on
  `NetworkInterfaceInfo`, `active_speed_mbps` and `supported_speed_mbps`, both
  defaulting to `None`. Append-only, so no existing consumer changes.
- `src/exo/utils/info_gatherer/system_info.py`:
  - `_get_active_speeds_mbps()` reads `psutil.net_if_stats()`. Cross-platform,
    no subprocess. psutil reports `0` when the OS exposes no speed, which is
    treated as unknown rather than as zero.
  - `_get_supported_speeds_mbps()` parses the "supported media" block of
    `ifconfig -v`, macOS only, and takes the fastest recognised media type per
    interface. An unrecognised media type is dropped rather than guessed at.
  - Both helpers sit above `get_network_interfaces()` and are wired into the
    existing `NetworkInterfaceInfo` construction.
  - The parsing is split into pure functions over injected data
    (`_active_speeds_from_stats`, `_parse_supported_media_mbps`) so it can be
    tested without a live network stack or a subprocess.
- `src/exo/utils/info_gatherer/tests/test_system_info.py`: new, 6 tests.

## Why It Works

Both fields default to `None`, and `None` means "not known" rather than "zero" —
so a platform that exposes neither number is indistinguishable from today's
behaviour, and no caller has to change.

`active_speed_mbps` comes from psutil and works on any platform that exposes a
speed. `supported_speed_mbps` is macOS-only by design, because `ifconfig -v` is
where that information lives on the platform exo primarily targets.

## Test Plan

### Manual Testing
- Hardware: Ubuntu x86_64, Python 3.13 (no Apple Silicon available)
- `psutil.net_if_stats()` reports `speed = 0` for every interface on this
  virtualised host (virtio; `/sys/class/net/eth0/speed` reads `-1`), so
  `active_speed_mbps` correctly comes back `None` here rather than `0`. That
  exercises the unknown-speed path but not the populated one.

### Automated Testing
New file `src/exo/utils/info_gatherer/tests/test_system_info.py`, 6 tests, no
MLX and no network:

- `_active_speeds_from_stats` maps interface to speed and drops `0` as unknown.
- `_parse_supported_media_mbps` against a synthetic `ifconfig -v` sample, taking
  the fastest media type per interface.
- Unrecognised media types dropped rather than guessed.
- Empty input returns an empty mapping.

## What is not verified

I want to be direct about this rather than let a reviewer find it.

`_parse_supported_media_mbps` was written against the documented BSD `ifconfig`
output format, **not** against a real macOS capture — there is no Apple hardware
available to me. Its docstring says so in the source as well. The function is
written to fail closed: anything it does not recognise is omitted, so a format
mismatch yields `None` rather than a wrong number. But it should be checked
against real `ifconfig -v` output before anyone relies on it.

`active_speed_mbps` has no such caveat. It goes through psutil, is
platform-independent, and its parsing is covered by the tests above.

If you would rather not carry an unverified parser, I am happy to split this:
land `active_speed_mbps` on its own and hold `supported_speed_mbps` until
someone with a Mac can paste `ifconfig -v` output. Say the word and I will
reshape it.
```
