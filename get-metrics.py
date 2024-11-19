#!/usr/bin/env python

import json
import re
import subprocess
import sys

def main():
    vm_machines = get_vm_machines()

    metrics = {}

    for vm in vm_machines:
        vm_metrics = get_metrics(vm)
        
        if vm_metrics is None:
            continue

        vm_metrics.update({ "rctl" : get_rctl(vm) })

        metrics.update({ vm : vm_metrics })

    print(json.dumps(metrics, indent=4))

    return 0

def get_rctl(vm):
    process = get_output("pgrep", "-f", f"bhyve: {vm}")

    if process.stdout == "":
        return None

    pid = int(process.stdout)

    rctl = get_output("rctl", "-u", f"process:{pid}")

    if rctl.stdout == "":
        return None

    raw_lines = rctl.stdout.splitlines()

    rctl_metrics = {}

    for line in raw_lines:
        (key, value) = line.split("=", 1)

        rctl_metrics[key] = int(value)

    return rctl_metrics

def get_metrics(vm):
    process = get_output("vm", "info", vm)

    if process.stdout == "":
        return None

    raw_lines = process.stdout.splitlines()

    metrics = {}

    for line in raw_lines:
        match = re.search(r"^[^:]+: .+$", line.strip())

        if not match:
            continue

        raw_match = match.string[match.start():match.end()]
        raw_match = raw_match.split(":", 1)

        key = raw_match[0].strip()
        value = raw_match[1].strip()

        if key == "memory-resident":
            metrics["memory-usage"] = int(value.split(" ", 1)[0])
        elif key == "bytes-in":
            if "rx" not in metrics:
                metrics["rx"] = 0

            metrics["rx"] += int(value.split(" ", 1)[0])
        elif key == "bytes-out":
            if "tx" not in metrics:
                metrics["tx"] = 0

            metrics["tx"] += int(value.split(" ", 1)[0])
        elif key == "bytes-used":
            if "storage-usage" not in metrics:
                metrics["storage-usage"] = 0

            metrics["storage-usage"] += int(value.split(" ", 1)[0])

    return metrics

def get_vm_machines():
    process = get_output("pgrep", "-fl", "^bhyve: vm[0-9][0-9][0-9]$")

    if process.stdout == "":
        return []

    raw_lines = process.stdout.splitlines()

    for line in raw_lines:
        match = re.search(r"vm[0-9][0-9][0-9]$", line)

        name = match.string[match.start():match.end()]

        yield name

def get_output(*args):
    return subprocess.run(args, stdout=subprocess.PIPE, text=True)

if __name__ == "__main__":
    sys.exit(main())
