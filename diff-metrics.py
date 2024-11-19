#!/usr/bin/env python

import json
import os
import subprocess
import sys

BASEDIR = os.path.join(".", os.path.dirname(sys.argv[0]))
BASEDIR = os.path.realpath(BASEDIR)

# See sysexits(3).
EX_OK = 0
EX_USAGE = 64
EX_DATAERR = 65
EX_NOINPUT = 66
EX_NOUSER = 67
EX_NOHOST = 68
EX_UNAVAILABLE = 69
EX_SOFTWARE = 70
EX_OSERR = 71
EX_OSFILE = 72
EX_CANTCREAT = 73
EX_IOERR = 74
EX_TEMPFAIL = 75
EX_PROTOCOL = 76
EX_NOPERM = 77
EX_CONFIG = 78

def main(*args):
    if len(args) < 2:
        usage()
        return EX_USAGE

    a_metrics_file = args[1]

    if not os.path.isfile(a_metrics_file):
        err(f"Cannot find File '{a_metrics_file}'")
        return EX_NOINPUT
    
    with open(a_metrics_file) as fd:
        a_metrics = json.loads(fd.read())

    process = get_output(f"{BASEDIR}/get-metrics.py")

    if process.stdout == "":
        return EX_SOFTWARE

    b_metrics = json.loads(process.stdout)

    diff_metrics = {}

    for vm, metrics in a_metrics.items():
        if vm not in b_metrics:
            continue

        diff_metrics[vm] = {}

        for metric in metrics:
            if metric not in b_metrics[vm]:
                continue

            if metric == "rctl" and isinstance(metrics[metric], dict):
                diff_metrics[vm][metric] = {}

                for rctl_key, rctl_value in metrics[metric].items():
                    if rctl_key not in b_metrics[vm][metric]:
                        continue

                    diff_metrics[vm][metric][rctl_key] = abs(metrics[metric][rctl_key]-b_metrics[vm][metric][rctl_key])
            else:
                diff_metrics[vm][metric] = abs(metrics[metric]-b_metrics[vm][metric])

    print(json.dumps(diff_metrics, indent=4))

    return EX_OK

def get_output(*args):
    return subprocess.run(args, stdout=subprocess.PIPE, text=True)

def warn(msg):
    print(f"##!> {msg} <!##", file=sys.stderr)

def err(msg):
    print(f"###> {msg} <###", file=sys.stderr)

def info(msg):
    print(f"======> {msg} <======", file=sys.stderr)

def usage():
    print("usage: diff-metrics.py <metrics-file>")

if __name__ == "__main__":
    sys.exit(main(*sys.argv))
