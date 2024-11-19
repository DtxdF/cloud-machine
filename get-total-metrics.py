#!/usr/bin/env python

import json
import os
import subprocess
import sys

BASEDIR = os.path.join(".", os.path.dirname(sys.argv[0]))
BASEDIR = os.path.realpath(BASEDIR)

def main():
    metrics = {}

    process = get_output(
        os.path.join(BASEDIR, "get-metrics.py")
    )

    if process.stdout == "":
        print(json.dumps(metrics))
        return 0

    metrics_by_vm = json.loads(process.stdout)

    metrics = {
        "memory-usage" : 0,
        "rx" : 0,
        "tx" : 0,
        "storage-usage" : 0,
        "rctl" : {
            "cputime" : 0,
            "datasize" : 0,
            "stacksize" : 0,
            "coredumpsize" : 0,
            "memoryuse" : 0,
            "memorylocked" : 0,
            "maxproc" : 0,
            "openfiles" : 0,
            "vmemoryuse" : 0,
            "nthr" : 0,
            "nsemop" : 0,
            "wallclock" : 0,
            "pcpu" : 0,
            "readbps" : 0,
            "writebps" : 0,
            "readiops" : 0,
            "writeiops" : 0
        }
    }

    for vm_metrics in metrics_by_vm.values():
        for metric in vm_metrics.keys():
            if metric == "rctl":
                for rctl_metric in vm_metrics[metric].keys():
                    metrics[metric][rctl_metric] += vm_metrics[metric][rctl_metric]
            else:
                metrics[metric] += vm_metrics[metric]

    print(json.dumps(metrics, indent=4))

    return 0

def get_output(*args):
    return subprocess.run(args, stdout=subprocess.PIPE, text=True)

if __name__ == "__main__":
    sys.exit(main())
