#!/usr/bin/env python3
"""Bounded macOS UI benchmark; synthetic files, no observer or live sessions."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import subprocess
import time


def fixture(count, layout):
    now = time.time()
    missions = [{"id": f"mission-{i}", "title": f"Synthetic mission {i}",
                 "goal": "Inspect a synthetic outcome", "checkpoints": []}
                for i in range(count if layout == "missions" else 1)]
    agents = [{"id": f"worker-{i}", "missionId": f"mission-{i if layout == 'missions' else 0}",
               "name": f"Synthetic worker {i}", "provider": "Example", "status": "working",
               "summary": "Synthetic CPU measurement", "lastActivity": now, "lastProgress": now,
               "trajectory": "unknown", "evidence": "", "nextStep": "Inspect"}
              for i in range(count)]
    return {"generatedAt": now, "demo": False, "missions": missions, "agents": agents,
            "warnings": [], "queue": []}


def write_state(state, feed):
    feed["generatedAt"] = time.time()
    temporary = state.with_suffix(".tmp")
    temporary.write_text(json.dumps(feed))
    os.replace(temporary, state)


def usage(pid):
    fields = subprocess.check_output(["ps", "-p", str(pid), "-o", "time=,rss="], text=True).split()
    seconds = 0.0
    for part in fields[0].split(":"):
        seconds = seconds * 60 + float(part)
    return seconds, int(fields[1]) / 1024


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, required=True,
                        help="Bundle built with --bundle-id local.sneakpeek.performance")
    parser.add_argument("--output", type=Path, required=True, help="New results directory")
    parser.add_argument("--counts", type=int, nargs="+", default=[1, 100, 1000])
    parser.add_argument("--layout", choices=["missions", "team"], default="team")
    parser.add_argument("--appearance", choices=["native", "otter"], default="native")
    parser.add_argument("--seconds", type=int, default=12)
    args = parser.parse_args()
    if not 5 <= args.seconds <= 60 or not all(1 <= n <= 5000 for n in args.counts):
        parser.error("Use 5–60 measurement seconds and 1–5,000 agents per case")
    app = args.app.resolve()
    identifier = "local.sneakpeek.performance"
    with (app / "Contents/Info.plist").open("rb") as stream:
        if plistlib.load(stream).get("CFBundleIdentifier") != identifier:
            parser.error("A separate local.sneakpeek.performance bundle is required; live apps are never closed")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for count in args.counts:
        directory = output / str(count)
        directory.mkdir()
        state = directory / "state.json"
        feed = fixture(count, args.layout)
        write_state(state, feed)
        command = [str(app / "Contents/MacOS/SneakPeek"), "--state", str(state),
                   "--no-bridge", "--expanded", "--" + args.appearance]
        if args.layout == "team":
            command.append("--render-raft")
        with (directory / "stderr.log").open("w") as log:
            process = subprocess.Popen(command, stdout=log, stderr=log)
            try:
                for _ in range(5):
                    write_state(state, feed)
                    time.sleep(1)
                if process.poll() is not None:
                    raise RuntimeError("Profiling app exited early; close any existing profiling instance and retry")
                start_cpu, _ = usage(process.pid)
                start = time.monotonic()
                for _ in range(args.seconds):
                    write_state(state, feed)
                    time.sleep(1)
                elapsed = time.monotonic() - start
                end_cpu, rss = usage(process.pid)
                row = {"agents": count, "missions": len(feed["missions"]), "layout": args.layout,
                       "appearance": args.appearance, "seconds": round(elapsed, 2),
                       "cpuPercentOneCore": round(100 * (end_cpu - start_cpu) / elapsed, 2),
                       "rssMiB": round(rss, 1)}
                rows.append(row)
                (output / "results.json").write_text(json.dumps(rows, indent=2) + "\n")
                print(json.dumps(row), flush=True)
            finally:
                # Only the dedicated process started above may be quit. A duplicate
                # launch exits early and must not close a pre-existing instance.
                if process.poll() is None:
                    try:
                        subprocess.run(["osascript", "-e", "with timeout of 3 seconds", "-e",
                                        f'tell application id "{identifier}" to quit', "-e", "end timeout"],
                                       stdout=log, stderr=log, timeout=5, check=True)
                        process.wait(timeout=3)
                    except (subprocess.SubprocessError, OSError):
                        if process.poll() is None:
                            process.terminate()
                            try:
                                process.wait(timeout=3)
                            except subprocess.TimeoutExpired:
                                process.kill()
                                process.wait()


if __name__ == "__main__":
    main()
