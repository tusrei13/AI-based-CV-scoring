"""Opt-in smoke script: chạy API thật nhiều lần để xem phân bố điểm.

Ví dụ: python scripts/run_live_distribution.py sample/sample_resume.pdf jd.txt --runs 3
"""

import argparse
import json
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument("pdf")
parser.add_argument("jd", nargs="", default="")
parser.add_argument("--runs", type=int, default=3)
args = parser.parse_args()
for index in range(args.runs):
    command = [sys.executable, "main.py", args.pdf]
    if args.jd:
        command.append(args.jd)
    command.extend(["--no-cache", "--json", f"live-run-{index + 1}.json"])
    subprocess.run(command, check=True)
print("Đã chạy xong; xem các file live-run-*.json để so sánh phân bố.")
