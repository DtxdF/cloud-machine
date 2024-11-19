#!/usr/bin/env python

import json
import re
import os
import subprocess
import sys

from humanfriendly import parse_size

def main():
    vm_machines = get_vm_machines()

    limits = {}

    for vm in vm_machines:
        vm_limits = get_limits(vm)
        
        if vm_limits is None:
            continue

        limits.update({ vm : vm_limits })

    print(json.dumps(limits, indent=4))

    return 0

def get_limits(vm):
    process = get_output("vm", "info", vm)

    if process.stdout == "":
        return None

    raw_lines = process.stdout.splitlines()

    limits = {}

    for line in raw_lines:
        match = re.search(r"^[^:]+: .+$", line.strip())

        if not match:
            continue

        raw_match = match.string[match.start():match.end()]
        raw_match = raw_match.split(":", 1)

        key = raw_match[0].strip()
        value = raw_match[1].strip()

        if key == "memory":
            limits["memory"] = parse_size(value.split(" ", 1)[0], binary=True)
        elif key == "bytes-size":
            if "storage" not in limits:
                limits["storage"] = 0

            limits["storage"] += int(value.split(" ", 1)[0])

    return limits

def get_vm_machines():
    process = get_output("sysrc", "-ni", "vm_dir")

    if process.stdout == "":
        return []

    vm_bhyve_dir = process.stdout.rstrip()

    next_vm = 1

    while True:
        if next_vm >= 999:
            break

        vm_name = "vm%003d" % next_vm

        vm_dir = os.path.join(
            vm_bhyve_dir, vm_name
        )

        if os.path.isdir(vm_dir):
            yield vm_name

        next_vm += 1

def get_output(*args):
    return subprocess.run(args, stdout=subprocess.PIPE, text=True)

if __name__ == "__main__":
    sys.exit(main())
