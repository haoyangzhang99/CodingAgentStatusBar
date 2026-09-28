#!/usr/bin/env python3
"""
Dashboard Performance Profiler

Runs the dashboard with cProfile and memory profiling to identify bottlenecks.
Generates detailed reports on CPU and memory usage.

Usage:
    python tools/profile_dashboard.py [--duration SECONDS] [--output FILE]
"""

import sys
import os
import cProfile
import pstats
import tracemalloc
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt6.QtWidgets import QApplication
from opencode_status_bar.dashboard.window import DashboardWindow


def profile_dashboard_startup(duration_seconds: int = 30) -> tuple[pstats.Stats, tuple]:
    tracemalloc.start()

    profiler = cProfile.Profile()
    profiler.enable()

    app = QApplication(sys.argv)
    window = DashboardWindow()
    window.show()

    start_time = time.time()
    while time.time() - start_time < duration_seconds:
        app.processEvents()
        time.sleep(0.01)

    profiler.disable()

    snapshot = tracemalloc.take_snapshot()
    tracemalloc.stop()

    stats = pstats.Stats(profiler)
    stats.strip_dirs()
    stats.sort_stats("cumulative")

    return stats, (snapshot, start_time)


def analyze_memory_snapshot(snapshot, start_time: float) -> None:
    print("\n" + "=" * 80)
    print("MEMORY USAGE ANALYSIS")
    print("=" * 80)

    top_stats = snapshot.statistics("lineno")

    print("\n[ Top 20 Memory Allocations ]")
    for stat in top_stats[:20]:
        print(f"{stat.size / 1024 / 1024:>8.1f} MB | {stat.count:>6} allocs | {stat}")

    total_mb = sum(stat.size for stat in top_stats) / 1024 / 1024
    print(f"\nTotal: {total_mb:.1f} MB")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Profile dashboard performance")
    parser.add_argument(
        "--duration", type=int, default=30, help="Profiling duration in seconds"
    )
    parser.add_argument(
        "--output", type=str, default="dashboard_profile.txt", help="Output file"
    )

    args = parser.parse_args()

    print(f"Profiling dashboard for {args.duration} seconds...")
    print("Dashboard will open. Interact normally (switch tabs, refresh, etc.)")

    stats, memory_data = profile_dashboard_startup(args.duration)

    print("\n" + "=" * 80)
    print("CPU PROFILING RESULTS")
    print("=" * 80)

    print("\n[ Top 30 Functions by Cumulative Time ]")
    stats.print_stats(30)

    print("\n[ Top 30 Functions by Total Time ]")
    stats.sort_stats("time")
    stats.print_stats(30)

    analyze_memory_snapshot(*memory_data)

    with open(args.output, "w") as f:
        stats.dump_stats(args.output)

    print(f"\nFull report saved to: {args.output}")


if __name__ == "__main__":
    main()
