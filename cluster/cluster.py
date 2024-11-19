#!/usr/bin/env python

import argparse
import json
import random
import re
import shlex
import signal
import statistics
import subprocess
import sys
import time
import os

import commentjson
import greenstalk
import tcp_latency

from humanfriendly import parse_timespan, parse_size

BASEDIR = os.path.join(".", os.path.dirname(sys.argv[0]))
BASEDIR = os.path.realpath(BASEDIR)
CONFIG = f"{BASEDIR}/settings.json"

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

# Defaults.
DEFAULT_NODE_ID = "default"
DEFAULT_PROFILE = "CS0"
DEFAULT_PROFILES = ("CS0", "CS1", "CS2", "CS3", "CS4", "CS5")
DEFAULT_LOCAL = "127.0.0.1"
DEFAULT_REPORTER = "127.0.0.1"
DEFAULT_PORT = 11300
DEFAULT_SELECT_ALGO = "less-latency"
DEFAULT_SELECT_ALGOS = ("all", "random", "less-latency", "single")
DEFAULT_SELECT_ARG = None
DEFAULT_TTR = 60 * 60 * 1 # 1h
DEFAULT_SCRIPTS = os.path.join(BASEDIR, "..")
DEFAULT_SCRIPTS = os.path.realpath(DEFAULT_SCRIPTS)
DEFAULT_FORWARD_MAX = 16
DEFAULT_METRICS_DELAY = 60 * 5 # 5m
DEFAULT_METRICS_SKEW = 6

class InvalidAlgorithm(Exception):
    pass

class ArgumentRequired(Exception):
    pass

class HostNotFound(Exception):
    pass


def main(argv):
    try:
        config = getconfig(CONFIG)
    except Exception as e:
        raise
        err("Error parsing configuration file: %s" % e)
        return EX_CONFIG

    hosts = config.get("hosts")

    if not hosts:
        err("No hosts has been defined!")
        return EX_CONFIG

    if len(argv) < 2:
        usage()
        return EX_USAGE

    cmd = argv[1]
    args = argv[1:]

    try:
        if cmd == "create":
            return cmd_create(args, config)
        elif cmd == "logs":
            return cmd_logs(args, config)
        elif cmd == "status":
            return cmd_status(args, config)
        elif cmd == "worker":
            return cmd_worker(args, config)
        elif cmd == "destroy":
            return cmd_destroy(args, config)
        elif cmd == "metrics":
            return cmd_metrics(args, config)
        else:
            usage()
            return EX_USAGE
    except KeyboardInterrupt:
        return EX_SOFTWARE
    except Exception as e:
        raise
        err("Exception: %s" % e)
        return EX_SOFTWARE

def cmd_create(argv, config):
    parser = argparse.ArgumentParser(
        prog=argv[0],
        description="Create a job for virtual machine creation"
    )

    parser.add_argument("--options",
        help="Options for the virtual machine"
    )
    parser.add_argument("--profile",
        help="Profile with resources to allocate (default: %(default)s)",
        default=config.get("default-profile"),
        choices=config.get("profiles")
    )
    parser.add_argument("--select-algo",
        help="Selection algorithm (default: %(default)s)",
        default=config.get("select-algo"),
        choices=DEFAULT_SELECT_ALGOS
    )
    parser.add_argument("--select-arg",
        help="Selection argument",
        default=config.get("select-arg")
    )
    parser.add_argument("--tags",
        help="Tags to find virtual machines in some operations",
        required=True
    )

    args = parser.parse_args(argv[1:])

    profile = args.profile
    options = args.options
    select_algo = args.select_algo
    select_arg = args.select_arg
    tags = args.tags

    if options is not None:
        options = shlex.split(options)

    tags = tags.split()

    message = {
        "profile" : profile,
        "options" : options,
        "tags" : tags
    }

    hosts = select_hosts(config.get("hosts"), select_algo, select_arg)

    for host in hosts:
        (host, port) = host

        try:
            put(message, "create", host, port, config)
        except Exception as e:
            warn("Exception: %s" % e)

    return EX_OK

def cmd_logs(argv, config):
    logs = {}

    logdir = os.path.join(
        BASEDIR, "logs"
    )

    logs_files = []

    if os.path.isdir(logdir):
        logs_files = sorted(os.listdir(logdir))

    for log_file in logs_files:
        (log_time_str, _) = os.path.splitext(log_file)

        log_file = os.path.join(logdir, log_file)

        with open(log_file) as fd:
            try:
                logs[log_time_str] = json.loads(fd.read())
            except Exception as e:
                warn("Error reading log '%s': %s" % (log_file, e))

    print(json.dumps(logs, indent=4))

    return EX_OK

def cmd_status(argv, config):
    reporter = config.get("reporter")
    (host, port) = parse_host(reporter)

    (job, message, client) = watch("status", host, port, parse_json=False)

    logdir = os.path.join(
        BASEDIR, "logs"
    )

    if not os.path.isdir(logdir):
        os.makedirs(logdir, exist_ok=True)

    logs = config.get("logs")

    remove_after = logs.get("remove-after")

    remove_after_years = remove_after.get("years")
    remove_after_days = remove_after.get("days")
    remove_after_hours = remove_after.get("hours")
    remove_after_minutes = remove_after.get("minutes")
    remove_after_seconds = remove_after.get("seconds")
    remove_after_weeks = remove_after.get("weeks")
    remove_count = remove_after.get("count")

    logs_files = os.listdir(logdir)

    if remove_count is not None and \
            len(logs_files) > remove_count:
        logs_toremove = set(logs_files[:remove_count])
    else:
        logs_toremove = set()

    if remove_after_years is not None \
            or remove_after_days is not None \
            or remove_after_hours is not None \
            or remove_after_minutes is not None \
            or remove_after_seconds is not None \
            or remove_after_weeks is not None:
        for log_file in logs_files:
            (log_time_str, _) = os.path.splitext(log_file)

            log_time = int(log_time_str)

            _gt = lambda s: (time.time() - log_time) > s

            if remove_after_years is not None \
                    and _gt(remove_after_years):
                logs_toremove.add(log_file)
                continue

            if remove_after_days is not None \
                    and _gt(remove_after_days):
                logs_toremove.add(log_file)
                continue

            if remove_after_hours is not None \
                    and _gt(remove_after_hours):
                logs_toremove.add(log_file)
                continue

            if remove_after_minutes is not None \
                    and _gt(remove_after_minutes):
                logs_toremove.add(log_file)
                continue

            if remove_after_seconds is not None \
                    and _gt(remove_after_seconds):
                logs_toremove.add(log_file)
                continue

            if remove_after_weeks is not None \
                    and _gt(remove_after_weeks):
                logs_toremove.add(log_file)
                continue

    for log_toremove in logs_toremove:
        info("Removing log '%s'" % log_toremove)

        try:
            os.remove(
                os.path.join(logdir, log_toremove)
            )
        except Exception as e:
            warn("Error removing log '%s': %s" % (log_toremove, e))

    log = os.path.join(
        logdir, time.strftime("%s.json")
    )

    info("Creating log file: %s" % log)

    with open(log, "w") as fd:
        fd.write(message)

    client.delete(job)

    client.close()

    return EX_OK

def cmd_worker(argv, config):
    parser = argparse.ArgumentParser(
        prog=argv[0],
        description="Create a job for virtual machine creation"
    )

    parser.add_argument("--tube",
        help="Stay in this tube for operations",
        choices=("create", "destroy", "forward"),
        required=True
    )

    args = parser.parse_args(argv[1:])

    tube = args.tube

    local = config.get("local")

    (host, port) = parse_host(local)

    (job, message, client) = watch(tube, host, port)

    if tube == "create":
        return cmd_worker_create(job, message, client, config)
    elif tube == "destroy":
        return cmd_worker_destroy(job, message, client, config)
    elif tube == "forward":
        return cmd_worker_forward(job, message, client, config)
    else:
        return EX_OK

def cmd_worker_create(job, message, client, config):
    reporter = config.get("reporter")
    (reporter_host, reporter_port) = parse_host(reporter)
    
    if not check_limits(config.get("limits")) or \
            not check_overload(config.get("overload")):
        warn("Limits has been reached!")

        forward = config.get("forward")

        forward_next = forward.get("next")

        if forward_next is not None:
            (host, port) = parse_host(forward_next)

            status = "Forwarding message to %s:%d" % (host, port)

            warn(status)

            forward_max = forward.get("max")

            forward_message = {
                "max" : forward_max - 1,
                "message" : message
            }

            try:
                put(forward_message, "forward", host, port, config)
            except Exception as e:
                status = "Exception while forwarding message to %s:%d: %s" % (host, port, e)

                warn(status)
        else:
            status = "Could not forward the message because no node has been set!"

            warn(status)

        client.delete(job)

        client.close()

        info("Reporting status")

        message = {
            "node-id" : config.get("node-id"),
            "forwarded" : forward_next,
            "status" : status,
            "context" : "create.forward"
        }

        put(message, "status", reporter_host, reporter_port, config)

        return EX_OK

    profile = message.get("profile")
    
    options = message.get("options")

    tags = message.get("tags")

    scripts = config.get("scripts")

    args = [
        os.path.join(scripts, "timeout.sh"),
        "%d" % (config.get("ttr") - 2),
        os.path.join(scripts, "safe-deploy.sh"),
        profile,
        "tags=%s" % " ".join(tags)
    ]

    if options is not None:
        args.extend(options)

    info("Creating a new virtual machine")

    process = subprocess.run(args,
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
        text=True
    )

    client.delete(job)

    client.close()

    message = {
        "node-id" : config.get("node-id"),
        "status" : process.returncode,
        "output" : process.stdout,
        "tags" : tags,
        "context" : "create"
    }

    info("Reporting status")

    put(message, "status", reporter_host, reporter_port, config)

    return EX_OK

def cmd_worker_destroy(job, message, client, config):
    tags = message.get("tags")

    scripts = config.get("scripts")

    reporter = config.get("reporter")
    (host, port) = parse_host(reporter)

    ttr = config.get("ttr")
    ttr //= 2

    args = [
        os.path.join(scripts, "timeout.sh"),
        "%d" % (ttr - 2),
        os.path.join(scripts, "find.sh")
    ]

    args.extend(tags)

    info("Finding virtual machines")

    process = subprocess.run(args, capture_output=True, text=True)

    vms = process.stdout.splitlines()

    result = {}

    if process.returncode == 0 and len(vms) > 0:
        for vm in vms:
            warn("Destroying virtual machine (vm:%s)" % vm)

            args = [
                os.path.join(scripts, "timeout.sh"),
                "%d" % (ttr - 2),
                os.path.join(scripts, "destroy.sh"),
                vm
            ]

            process = subprocess.run(args,
                          capture_output=True,
                          text=True
                      )

            rc = process.returncode
            stdout = process.stdout
            stderr = process.stderr

            result[vm] = {
                "status" : rc,
                "stdout" : stdout,
                "stderr" : stderr
            }
    else:
        rc = process.returncode
        stdout = process.stdout
        stderr = process.stderr

        result["<not-found>"] = {
            "status" : rc,
            "stdout" : stdout,
            "stderr" : stderr
        }

        warn("No virtual machines to destroy found.")

    client.delete(job)

    client.close()

    message = {
        "node-id" : config.get("node-id"),
        "context" : "destroy",
        "destroyed" : result
    }

    info("Reporting status")

    put(message, "status", host, port, config)

    return EX_OK

def cmd_worker_forward(job, message, client, config):
    forward_message = message

    forward_max = forward_message.get("max")

    if forward_max <= 0:
        warn("Maximum number of forwarding reached!")

        return EX_OK

    message = forward_message.get("message")

    return cmd_worker_create(job, message, client, config)

def cmd_destroy(argv, config):
    parser = argparse.ArgumentParser(
        prog=argv[0],
        description="Create a job for virtual machine destruction"
    )

    parser.add_argument("--target",
        help="Destroy virtual machines in this host"
    )
    parser.add_argument("--tags",
        help="Destroy virtual machines that match with these tags",
        required=True
    )

    args = parser.parse_args(argv[1:])

    target = args.target
    tags = args.tags

    tags = tags.split()

    message = {
        "tags" : tags
    }

    if target is None:
        targets = config.get("hosts")
    else:
        targets = [parse_host(target)]

    for target in targets:
        (host, port) = target

        try:
            put(message, "destroy", host, port, config)
        except Exception as e:
            warn("Exception: %s" % e)

    return EX_OK

def cmd_metrics(argv, config):
    metrics_config = config.get("metrics")

    delay = metrics_config.get("delay")
    skew = metrics_config.get("skew")

    if delay > 0:
        info("Sleeping %d seconds (delay)" % delay)

        time.sleep(delay)

    if skew > 0:
        skew = random.randint(1, skew)

        info("Sleeping %d seconds (skew)" % skew)

        time.sleep(skew)

    reporter = config.get("reporter")
    (host, port) = parse_host(reporter)

    info("Retrieving metrics")

    prog = os.path.join(BASEDIR, "../get-metrics.py")

    process = subprocess.run([prog],
                  capture_output=True,
                  text=True
              )

    if process.stdout == "":
        metrics = {}
    else:
        metrics = json.loads(process.stdout)

    message = {
        "node-id" : config.get("node-id"),
        "context" : "metrics",
        "status" : process.returncode,
        "stdout" : metrics,
        "stderr" : process.stderr
    }

    info("Reporting status")

    put(message, "status", host, port, config)

    return EX_OK

def select_hosts(hosts, algo, arg):
    selected_hosts = []

    if algo == "all":
        info("selection:%s = all hosts available" % algo)

        selected_hosts.extend(hosts)
    elif algo == "random":
        host = random.choice(hosts)

        info("selection:%s = %s:%d" % (algo, host[0], host[1]))

        selected_hosts.append(host)
    elif algo == "less-latency":
        less_latency = 0
        selected = None

        for host in hosts:
            if host[0] == "127.0.0.1" or \
                    host[0] == "localhost":
                selected = host
                break

            latencies = tcp_latency.measure_latency(host[0], host[1], runs=4)

            if not latencies:
                continue

            latency = statistics.mean(latencies)

            if less_latency == 0 or latency < less_latency:
                less_latency = latency
                selected = host

        host = selected

        if host is None:
            raise HostNotFound("Match not found!")

        info("selection:%s = %s:%d" % (algo, host[0], host[1]))

        selected_hosts.append(host)
    elif algo == "single":
        if arg is None:
            raise ArgumentRequired("'single' algorithm requires an argument!")

        selected = None

        (selected_host, selected_port) = parse_host(arg)

        for host in hosts:
            if host[0] == selected_host and \
                    host[1] == selected_port:
                selected = host
                break

        host = selected

        if host is None:
            raise HostNotFound(f"Match not found for host '{selected_host}:{selected_port}'")

        info("selection:%s = %s:%d" % (algo, host[0], host[1]))

        selected_hosts.append(host)
    else:
        raise InvalidAlgorithm(f"Invalid algorithm '{algo}'")

    return selected_hosts

def watch(tube, host, port, parse_json=True):
    client = connect(host, port)

    info("Watching (tube:%s)" % tube)

    client.watch(tube)

    job = client.reserve()

    info("Reserved (job:%d)" % job.id)

    json_message = job.body

    if parse_json:
        message = json.loads(json_message)
    else:
        message = json_message

    return (job, message, client)

def put(message, tube, host, port, config):
    client = connect(host, port)

    info("Using (tube:%s)" % tube)

    client.use(tube)

    json_message = json.dumps(message)

    ttr = config.get("ttr")

    info("Creating job (ttr:%d)" % ttr)

    job = client.put(json_message, ttr=ttr)

    client.close()

    return job

def connect(host, port):
    info("Connecting (%s:%d)" % (host, port))

    return greenstalk.Client((host, port))

def getconfig(config):
    with open(config) as fd:
        config = commentjson.loads(fd.read())

    config = checkconfig(config)

    return config

def checkconfig(config):
    safe_config = {}

    keys = (
        "node-id",
        "default-profile",
        "profiles",
        "select-algo",
        "select-arg",
        "local",
        "reporter",
        "hosts",
        "ttr",
        "scripts",
        "forward",
        "limits",
        "overload",
        "metrics",
        "logs"
    )

    for k2 in config.keys():
        if k2 not in keys:
            raise KeyError(f"Key '{k2}' is not valid.")

    node_id = config.get("node-id", DEFAULT_NODE_ID)

    if not isinstance(node_id, str):
        raise TypeError("Key 'node-id' must be a string.")

    default_profile = config.get("default-profile", DEFAULT_PROFILE)

    if not isinstance(default_profile, str):
        raise TypeError("Key 'default-profile' must be a string.")

    profiles = config.get("profiles", DEFAULT_PROFILES)

    if not isinstance(profiles, list):
        raise TypeError("Key 'profiles' must be a list.")

    for nro, profile in enumerate(profiles, 1):
        if profile is None:
            raise TypeError(f"Profile #{nro} is null!")
        elif isinstance(profile, str):
            pass
        else:
            raise TypeError(f"Profile #{nro}:{profile} has an invalid type!")

    select_algo = config.get("select-algo", DEFAULT_SELECT_ALGO)

    if not isinstance(select_algo, str):
        raise TypeError("Key 'select-algo' must be a string.")

    select_arg = config.get("select-arg", DEFAULT_SELECT_ARG)

    if select_arg is not None and \
            not isinstance(select_arg, str):
        raise TypeError("Key 'select-arg' must be a string.")

    local = config.get("local", DEFAULT_LOCAL)

    if not isinstance(local, str):
        raise TypeError("Key 'local' must be a string.")

    reporter = config.get("reporter", DEFAULT_REPORTER)

    if not isinstance(reporter, str):
        raise TypeError("Key 'reporter' must be a string.")

    hosts = config.get("hosts", [])

    if not isinstance(hosts, list):
        raise TypeError("Key 'hosts' must be a list.")

    for nro, host in enumerate(hosts, 1):
        if host is None:
            raise TypeError(f"Host #{nro} is null!")
        elif isinstance(host, str):
            pass
        else:
            raise TypeError(f"Host #{nro}:{host} has an invalid type!")

    ttr = config.get("ttr", DEFAULT_TTR)

    if isinstance(ttr, str):
        ttr = parse_timespan(ttr)
    elif isinstance(ttr, int):
        pass
    else:
        raise TypeError("Key 'ttr' must be an integer.")

    scripts = config.get("scripts", DEFAULT_SCRIPTS)

    if not isinstance(scripts, str):
        raise TypeError("Key 'scripts' must be a string.")

    forward = config.get("forward", {})

    if not isinstance(forward, dict):
        raise TypeError("Key 'forward' must be a dict.")

    forward_next = forward.get("next")

    if forward_next is not None and \
            not isinstance(forward_next, str):
        raise TypeError("Key 'forward.next' must be a string.")

    forward_max = forward.get("max", DEFAULT_FORWARD_MAX)

    if not isinstance(forward_max, int):
        raise TypeError("Key 'forward.max' must be an integer.")

    limits = config.get("limits", {})

    if not isinstance(limits, dict):
        raise TypeError("Key 'limits' must be a dict.")

    limits_keys = ("memory", "storage")

    for k2 in limits.keys():
        if k2 not in limits_keys:
            raise KeyError(f"Key 'limits.{k2}' is not valid.")

    limits_memory = limits.get("memory")

    if limits_memory is not None:
        if isinstance(limits_memory, str):
            limits_memory = parse_size(limits_memory, binary=True)
        elif isinstance(limits_memory, int):
            pass
        else:
            raise TypeError("Key 'limits.memory' must be an integer.")

    limits_storage = limits.get("storage")

    if limits_storage is not None:
        if isinstance(limits_storage, str):
            limits_storage = parse_size(limits_storage, binary=True)
        elif isinstance(limits_storage, int):
            pass
        else:
            raise TypeError("Key 'limits.storage' must be an integer.")

    overload = config.get("overload", {})

    if not isinstance(overload, dict):
        raise TypeError("Key 'overload' must be a dict.")

    overload_keys = ("memory-usage", "rx", "tx", "rctl")

    for k2 in overload.keys():
        if k2 not in overload_keys:
            raise KeyError(f"Key 'overload.{k2}' is not valid.")

    overload_memory_usage = overload.get("memory-usage")

    if overload_memory_usage is not None:
        if isinstance(overload_memory_usage, str):
            overload_memory_usage = parse_size(overload_memory_usage, binary=True)
        elif isinstance(overload_memory_usage, int):
            pass
        else:
            raise TypeError("Key 'overload.memory-usage' must be an integer.")

    overload_rx = overload.get("rx")

    if overload_rx is not None:
        if isinstance(overload_rx, str):
            overload_rx = parse_size(overload_rx, binary=True)
        elif isinstance(overload_rx, int):
            pass
        else:
            raise TypeError("Key 'overload.rx' must be an integer.")

    overload_tx = overload.get("tx")

    if overload_tx is not None:
        if isinstance(overload_tx, str):
            overload_tx = parse_size(overload_tx, binary=True)
        elif isinstance(overload_tx, int):
            pass
        else:
            raise TypeError("Key 'overload.tx' must be an integer.")

    overload_rctl = overload.get("rctl", {})

    if overload_rctl:
        if not isinstance(overload_rctl, dict):
            raise TypeError("Key 'overload.rctl' must be a dict.")

        overload_rctl_keys = (
            "cputime",
            "datasize",
            "stacksize",
            "coredumpsize",
            "memoryuse",
            "memorylocked",
            "maxproc",
            "openfiles",
            "vmemoryuse",
            "pseudoterminals",
            "swapuse",
            "nthr",
            "msgqqueued",
            "msgqsize",
            "nmsgq",
            "nsem",
            "nsemop",
            "nshm",
            "shmsize",
            "wallclock",
            "pcpu",
            "readbps",
            "writebps",
            "readiops",
            "writeiops"
        )

        for k2 in overload_rctl.keys():
            if k2 not in overload_rctl_keys:
                raise KeyError(f"Key 'overload.rctl.{k2}' is not valid.")

        overload_rctl_cputime = overload_rctl.get("cputime")

        if overload_rctl_cputime is not None:
            if isinstance(overload_rctl_cputime, str):
                overload_rctl_cputime = parse_timespan(overload_rctl_cputime)
            elif isinstance(overload_rctl_cputime, int):
                pass
            else:
                raise TypeError("Key 'overload.rctl.cputime' must be an integer.")

        overload_rctl_datasize = overload_rctl.get("datasize")

        if overload_rctl_datasize is not None:
            if isinstance(overload_rctl_datasize, str):
                overload_rctl_datasize = parse_size(overload_rctl_datasize, binary=True)
            elif isinstance(overload_rctl_datasize, int):
                pass
            else:
                raise TypeError("Key 'overload.rctl.datasize' must be an integer.")

        overload_rctl_stacksize = overload_rctl.get("stacksize")

        if overload_rctl_stacksize is not None:
            if isinstance(overload_rctl_stacksize, str):
                overload_rctl_stacksize = parse_size(overload_rctl_stacksize, binary=True)
            elif isinstance(overload_rctl_stacksize, int):
                pass
            else:
                raise TypeError("Key 'overload.rctl.stacksize' must be an integer.")

        overload_rctl_coredumpsize = overload_rctl.get("coredumpsize")

        if overload_rctl_coredumpsize is not None:
            if isinstance(overload_rctl_coredumpsize, str):
                overload_rctl_coredumpsize = parse_size(overload_rctl_coredumpsize, binary=True)
            elif isinstance(overload_rctl_coredumpsize, int):
                pass
            else:
                raise TypeError("Key 'overload.rctl.coredumpsize' must be an integer.")

        overload_rctl_memoryuse = overload_rctl.get("memoryuse")

        if overload_rctl_memoryuse is not None:
            if isinstance(overload_rctl_memoryuse, str):
                overload_rctl_memoryuse = parse_size(overload_rctl_memoryuse, binary=True)
            elif isinstance(overload_rctl_memoryuse, int):
                pass
            else:
                raise TypeError("Key 'overload.rctl.memoryuse' must be an integer.")

        overload_rctl_memorylocked = overload_rctl.get("memorylocked")

        if overload_rctl_memorylocked is not None:
            if isinstance(overload_rctl_memorylocked, str):
                overload_rctl_memorylocked = parse_size(overload_rctl_memorylocked, binary=True)
            elif isinstance(overload_rctl_memorylocked, int):
                pass
            else:
                raise TypeError("Key 'overload.rctl.memorylocked' must be an integer.")

        overload_rctl_maxproc = overload_rctl.get("maxproc")

        if overload_rctl_maxproc is not None and \
                not isinstance(overload_rctl_maxproc, int):
            raise TypeError("Key 'overload.rctl.maxproc' must be an integer.")

        overload_rctl_openfiles = overload_rctl.get("openfiles")

        if overload_rctl_openfiles is not None and \
                not isinstance(overload_rctl_openfiles, int):
            raise TypeError("Key 'overload.rctl.openfiles' must be an integer.")

        overload_rctl_vmemoryuse = overload_rctl.get("vmemoryuse")

        if overload_rctl_vmemoryuse is not None:
            if isinstance(overload_rctl_vmemoryuse, str):
                overload_rctl_vmemoryuse = parse_size(overload_rctl_vmemoryuse, binary=True)
            elif isinstance(overload_rctl_vmemoryuse, int):
                pass
            else:
                raise TypeError("Key 'overload.rctl.vmemoryuse' must be an integer.")

        overload_rctl_pseudoterminals = overload_rctl.get("pseudoterminals")

        if overload_rctl_pseudoterminals is not None and \
                not isinstance(overload_rctl_pseudoterminals, int):
            raise TypeError("Key 'overload.rctl.pseudoterminals' must be an integer.")

        overload_rctl_swapuse = overload_rctl.get("swapuse")

        if overload_rctl_swapuse is not None:
            if isinstance(overload_rctl_swapuse, str):
                overload_rctl_swapuse = parse_size(overload_rctl_swapuse, binary=True)
            elif isinstance(overload_rctl_swapuse, int):
                pass
            else:
                raise TypeError("Key 'overload.rctl.swapuse' must be an integer.")

        overload_rctl_nthr = overload_rctl.get("nthr")

        if overload_rctl_nthr is not None and \
                not isinstance(overload_rctl_nthr, int):
            raise TypeError("Key 'overload.rctl.nthr' must be an integer.")

        overload_rctl_nsem = overload_rctl.get("nsem")

        if overload_rctl_nsem is not None and \
                not isinstance(overload_rctl_nsem, int):
            raise TypeError("Key 'overload.rctl.nsem' must be an integer.")

        overload_rctl_nsemop = overload_rctl.get("nsemop")

        if overload_rctl_nsemop is not None and \
                not isinstance(overload_rctl_nsemop, int):
            raise TypeError("Key 'overload.rctl.nsemop' must be an integer.")

        overload_rctl_nshm = overload_rctl.get("nshm")

        if overload_rctl_nshm is not None and \
                not isinstance(overload_rctl_nshm, int):
            raise TypeError("Key 'overload.rctl.nshm' must be an integer.")

        overload_rctl_shmsize = overload_rctl.get("shmsize")

        if overload_rctl_shmsize is not None:
            if isinstance(overload_rctl_shmsize, str):
                overload_rctl_shmsize = parse_size(overload_rctl_shmsize, binary=True)
            elif isinstance(overload_rctl_shmsize, int):
                pass
            else:
                raise TypeError("Key 'overload.rctl.shmsize' must be an integer.")

        overload_rctl_wallclock = overload_rctl.get("wallclock")

        if overload_rctl_wallclock is not None:
            if isinstance(overload_rctl_wallclock, str):
                overload_rctl_wallclock = parse_timespan(overload_rctl_wallclock)
            elif isinstance(overload_rctl_wallclock, int):
                pass
            else:
                raise TypeError("Key 'overload.rctl.wallclock' must be an integer.")

        overload_rctl_pcpu = overload_rctl.get("pcpu")

        if overload_rctl_pcpu is not None and \
                not isinstance(overload_rctl_pcpu, int):
            raise TypeError("Key 'overload.rctl.pcpu' must be an integer.")

        overload_rctl_readbps = overload_rctl.get("readbps")

        if overload_rctl_readbps is not None:
            if isinstance(overload_rctl_readbps, str):
                overload_rctl_readbps = parse_size(overload_rctl_readbps, binary=True)
            elif isinstance(overload_rctl_readbps, int):
                pass
            else:
                raise TypeError("Key 'overload.rctl.readbps' must be an integer.")

        overload_rctl_writebps = overload_rctl.get("writebps")

        if overload_rctl_writebps is not None:
            if isinstance(overload_rctl_writebps, str):
                overload_rctl_writebps = parse_size(overload_rctl_writebps, binary=True)
            elif isinstance(overload_rctl_writebps, int):
                pass
            else:
                raise TypeError("Key 'overload.rctl.writebps' must be an integer.")

        overload_rctl_readiops = overload_rctl.get("readiops")

        if overload_rctl_readiops is not None and \
                not isinstance(overload_rctl_readiops, int):
            raise TypeError("Key 'overload.rctl.readiops' must be an integer.")

        overload_rctl_writeiops = overload_rctl.get("writeiops")

        if overload_rctl_writeiops is not None and \
                not isinstance(overload_rctl_writeiops, int):
            raise TypeError("Key 'overload.rctl.writeiops' must be an integer.")

        overload_rctl = {
            "cputime" : overload_rctl_cputime,
            "datasize" : overload_rctl_datasize,
            "stacksize" : overload_rctl_stacksize,
            "coredumpsize" : overload_rctl_coredump,
            "memoryuse" : overload_rctl_memoryuse,
            "memorylocked" : overload_rctl_memorylocked,
            "maxproc" : overload_rctl_maxproc,
            "openfiles" : overload_rctl_openfiles,
            "vmemoryuse" : overload_rctl_vmemoryuse,
            "pseudoterminals" : overload_rctl_pseudoterminals,
            "swapuse" : overload_rctl_swapuse,
            "nthr" : overload_rctl_nthr,
            "msgqqueued" : overload_rctl_msgqqueued,
            "msgqsize" : overload_rctl_msgqsize,
            "nmsgq" : overload_rctl_nmsgq,
            "nsem" : overload_rctl_nsem,
            "nsemop" : overload_rctl_nsemop,
            "nshm" : overload_rctl_nshm,
            "shmsize" : overload_rctl_shmsize,
            "wallclock" : overload_rctl_wallclock,
            "pcpu" : overload_rctl_pcpu,
            "readbps" : overload_rctl_readbps,
            "writebps" : overload_rctl_writebps,
            "readiops" : overload_rctl_readiops,
            "writeiops" : overload_rctl_writeiops
        }

    metrics = config.get("metrics", {})

    if not isinstance(metrics, dict):
        raise TypeError("Key 'metrics' must be a dict.")

    metrics_delay = metrics.get("delay", DEFAULT_METRICS_DELAY)

    if isinstance(metrics_delay, str):
        metrics_delay = parse_timespan(metrics_delay)
    elif isinstance(metrics_delay, int):
        pass
    else:
        raise TypeError("Key 'metrics.delay' must be an integer.")

    metrics_skew = metrics.get("skew", DEFAULT_METRICS_SKEW)

    if isinstance(metrics_skew, str):
        metrics_skew = parse_timespan(metrics_skew)
    elif isinstance(metrics_skew, int):
        pass
    else:
        raise TypeError("Key 'metrics.skew' must be an integer.")

    logs = config.get("logs", {})

    if not isinstance(metrics, dict):
        raise TypeError("Key 'logs' must be a dict.")

    logs_remove_after = logs.get("remove-after", {})

    if not isinstance(logs_remove_after, dict):
        raise TypeError("Key 'logs.remove-after' must be a dict.")

    logs_remove_after_years = logs_remove_after.get("years")

    if logs_remove_after_years is not None:
        if not isinstance(logs_remove_after_years, int):
            raise TypeError("Key 'logs.remove-after.years' must be an integer.")

        logs_remove_after_years = parse_timespan("%d year" % logs_remove_after_years)

    logs_remove_after_days = logs_remove_after.get("days")

    if logs_remove_after_days is not None:
        if not isinstance(logs_remove_after_days, int):
            raise TypeError("Key 'logs.remove-after.days' must be an integer.")

        logs_remove_after_days = parse_timespan("%d day" % logs_remove_after_days)

    logs_remove_after_hours = logs_remove_after.get("hours")

    if logs_remove_after_hours is not None:
        if not isinstance(logs_remove_after_hours, int):
            raise TypeError("Key 'logs.remove-after.hours' must be an integer.")

        logs_remove_after_hours = parse_timespan("%d hour" % logs_remove_after_hours)

    logs_remove_after_minutes = logs_remove_after.get("minutes")

    if logs_remove_after_minutes is not None:
        if not isinstance(logs_remove_after_minutes, int):
            raise TypeError("Key 'logs.remove-after.minutes' must be an integer.")

        logs_remove_after_minutes = parse_timespan("%d minute" % logs_remove_after_minutes)

    logs_remove_after_seconds = logs_remove_after.get("seconds")

    if logs_remove_after_seconds is not None and \
            not isinstance(logs_remove_after_seconds, int):
        raise TypeError("Key 'logs.remove-after.seconds' must be an integer.")

    logs_remove_after_weeks = logs_remove_after.get("weeks")

    if logs_remove_after_weeks is not None:
        if not isinstance(logs_remove_after_weeks, int):
            raise TypeError("Key 'logs.remove-after.weeks' must be an integer.")

        logs_remove_after_weeks = parse_timespan("%d week" % logs_remove_after_weeks)

    logs_remove_count = logs_remove_after.get("count")

    if logs_remove_count is not None and \
            not isinstance(logs_remove_count, int):
        raise TypeError("Key 'logs.remove-count' must be an integer.")

    safe_config["node-id"] = node_id
    safe_config["default-profile"] = default_profile
    safe_config["profiles"] = profiles
    safe_config["select-algo"] = select_algo
    safe_config["select-arg"] = select_arg
    safe_config["local"] = local
    safe_config["reporter"] = reporter
    safe_config["hosts"] = list(parse_hosts(hosts))
    safe_config["ttr"] = ttr
    safe_config["scripts"] = scripts
    safe_config["forward"] = {
        "next" : forward_next,
        "max" : forward_max
    }
    safe_config["limits"] = {
        "memory" : limits_memory,
        "storage" : limits_storage
    }
    safe_config["overload"] = {
        "memory-usage" : overload_memory_usage,
        "rx" : overload_rx,
        "tx" : overload_tx,
        "rctl" : overload_rctl
    }
    safe_config["metrics"] = {
        "delay" : metrics_delay,
        "skew" : metrics_skew
    }
    safe_config["logs"] = {
        "remove-after" : {
            "years" : logs_remove_after_years,
            "days" : logs_remove_after_days,
            "hours" : logs_remove_after_hours,
            "minutes" : logs_remove_after_minutes,
            "seconds" : logs_remove_after_seconds,
            "weeks" : logs_remove_after_weeks,
        },
        "count" : logs_remove_count
    }

    return safe_config

def parse_hosts(hosts):
    for host in hosts:
        yield parse_host(host)

def parse_host(host):
    if re.search(r":[0-9]+$", host):
        (host, port) = host.split(":", 1)

        return (host, int(port))
    else:
        return (host, DEFAULT_PORT)

def check_limits(limits):
    prog = os.path.join(BASEDIR, "../get-total-limits.py")

    process = subprocess.run([prog],
                  stdout=subprocess.PIPE,
                  stderr=subprocess.DEVNULL,
                  text=True
              )

    if process.stdout == "":
        return True

    current = json.loads(process.stdout)
    current_memory = current["memory"]
    current_storage = current["storage"]

    limits_memory = limits.get("memory")
    limits_storage = limits.get("storage")

    if limits_memory is not None:
        if current_memory >= limits_memory:
            info("limits.memory: %d >= %d = True" % (current_memory, limits_memory))

            return False
        else:
            info("limits.memory: %d >= %d = False" % (current_memory, limits_memory))

    if limits_storage is not None:
        if current_storage >= limits_storage:
            info("limits.storage: %d >= %d = True" % (current_storage, limits_storage))

            return False
        else:
            info("limits.storage: %d >= %d = False" % (current_storage, limits_storage))

    return True

def check_overload(overload):
    prog = os.path.join(BASEDIR, "../get-total-metrics.py")

    process = subprocess.run([prog],
                  stdout=subprocess.PIPE,
                  stderr=subprocess.DEVNULL,
                  text=True
              )

    if process.stdout == "":
        return True

    current = json.loads(process.stdout)

    for overload_name, overload_value in overload.items():
        if overload_value is None:
            continue

        if overload_name == "rctl":
            for rctl_name, rctl_value in overload_value.items():
                if rctl_value is None:
                    continue

                current_value = current[overload_name][rctl_name]

                if current_value >= rctl_value:
                    info("overload.rctl.%s: %d >= %d = True" % (rctl_name, current_value, rctl_value))

                    return False
                else:
                    info("overload.rctl.%s: %d >= %d = False" % (rctl_name, current_value, rctl_value))
        else:
            current_value = current[overload_name]

            if current_value >= overload_value:
                info("overload.%s: %d >= %d = True" % (overload_name, current_value, overload_value))

                return False
            else:
                info("overload.%s: %d >= %d = False" % (overload_name, current_value, overload_value))

    return True

def warn(msg):
    print(f"##!> {msg} <!##", file=sys.stderr)

def err(msg):
    print(f"###> {msg} <###", file=sys.stderr)

def info(msg):
    print(f"===> {msg} <===", file=sys.stderr)

def usage():
    print("usage: cluster.py create [--options <options>] [--profile <profile>] [--select-algo <algo>]")
    print("               [--select-arg <argument>] --tags <tags>")
    print("       cluster.py logs")
    print("       cluster.py status")
    print("       cluster.py worker --tube [create|destroy|forward]")
    print("       cluster.py destroy [--target <target>[:<port>]] --tags <value>")
    print("       cluster.py metrics")

if __name__ == "__main__":
    sys.exit(main(sys.argv))
