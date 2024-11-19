#!/usr/bin/env python

import json
import os
import subprocess
import sys

BASEDIR = os.path.join(".", os.path.dirname(sys.argv[0]))
BASEDIR = os.path.realpath(BASEDIR)

def main():
    limits = {}

    process = get_output(
        os.path.join(BASEDIR, "get-limits.py")
    )

    if process.stdout == "":
        print(json.dumps(limits))
        return 0

    limits_by_vm = json.loads(process.stdout)

    limits = {
        "memory" : 0,
        "storage" : 0
    }

    for vm_limits in limits_by_vm.values():
        for limit in vm_limits.keys():
            limits[limit] += vm_limits[limit]

    print(json.dumps(limits, indent=4))

    return 0

def get_output(*args):
    return subprocess.run(args, stdout=subprocess.PIPE, text=True)

if __name__ == "__main__":
    sys.exit(main())
