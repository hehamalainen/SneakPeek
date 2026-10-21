# Native UI performance investigation

## Finding and fix

The installed app was observed using 100.3% CPU before shutdown (100% means one
CPU core). Its observer used 3.4%. A subsequent live restart with one mission
and one agent used about 2% CPU. No stack profile of the original incident was
captured, so its precise trigger is unproven.

A separate synthetic test reproduced sustained full-core use in the native
Team tab with 1,000 agents in one mission. A stack profile showed repeated calls
to `PeekStore.selectedAgent`, `PeekStore.agents`, sorting, and SwiftUI layout.
Each card independently recomputed the selected agent, sorting the whole team
repeatedly. The eager stacks also laid out cards outside the viewport.

The fix resolves the selection once for the team view, resolves the mission once
before filtering its agents, and uses lazy vertical cards and horizontal Cove
pairs. A card and its optional details remain one lazy row. Priority ordering,
source filtering, and selected-agent behavior are unchanged.

## Measurements

Short local runs on an Apple Silicon Mac with 24 GB RAM and macOS 26.7.1. CPU is
process CPU time divided by elapsed wall time, expressed as a percentage of one
core. Each case settles for five seconds, then measures for twelve seconds,
refreshing a synthetic JSON snapshot once per second. The expanded Team tab is
visible, with Native appearance, no pending permission or attached artifact,
and no observer. Results are indicative, not release budgets or endurance tests.

| Agents in one mission | Original app CPU | Fixed app CPU |
| --- | ---: | ---: |
| 100 | 25.9% | 5.4% |
| 1,000 | 99.1% | 3.0% |

The fixed 1,000-agent case used about 85 MiB resident memory. Short-run noise
means the 100- and 1,000-agent rows are not a scaling curve. The original binary
is the previously installed release; the fixed binary uses the current source
plus this patch. Both use the same benchmark script and synthetic fixture.

The fixed 1,000-agent Otter/Raft case measured 4.0% CPU and about 96 MiB resident
memory under the same timing and refresh conditions. Synthetic Native and Otter
renders were visually inspected to confirm that lazy layout still displays the
cards and Cove pairs. All 108 Python and 60 Swift tests pass.

## Reproduce safely

Build a separate profiling bundle; the script rejects the live app's identifier.
It writes only synthetic state under the specified new output directory,
passes `--no-bridge`, and closes its own profiling process after each case.
Do not run multiple profiling instances at the same time.

```sh
./scripts/build.sh --scratch-path /private/tmp/sneakpeek-perf-build \
  --app /private/tmp/SneakPeek-Performance.app \
  --bundle-id local.sneakpeek.performance
python3 scripts/profile-ui.py \
  --app /private/tmp/SneakPeek-Performance.app \
  --output runtime/performance/team-run --layout team --counts 100 1000
```

Use `--appearance otter` to include Cove, `--layout missions` for one agent per
mission in the queue view, and `--seconds 60` for a longer measurement. Each
output directory contains `results.json`, synthetic snapshots, and app stderr.
Output is ignored by Git. For a hot-process stack profile, use macOS Activity
Monitor's **Sample Process** on the profiling app.

The large-team regression test checks priority, selection, source filtering,
and mission fallback. Existing tests cover freshness, missing feeds, permission
boundaries, and Cove state. Timing assertions stay outside CI to avoid flaky
hardware-dependent tests.

## Remaining limits

This fixes a demonstrated UI bottleneck. It does not establish the cause of
every possible warm-laptop incident or validate supervision of 1,000 live
agents. These tests exclude harness discovery, log ingestion, artifact hashing,
permission storms, long-duration growth, and human attention capacity. The app
still polls full snapshots. See [the scaling plan](scaling.md) for the remaining
work and required validation.
