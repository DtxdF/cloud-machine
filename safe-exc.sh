#!/bin/sh

BASEDIR=`dirname -- "$0"` || exit $?
BASEDIR=`realpath -- "${BASEDIR}"` || exit $?

. "${BASEDIR}/lib.subr"

# Signals
SIGNALS_IGNORED="SIGALRM SIGVTALRM SIGPROF SIGUSR1 SIGUSR2"
SIGNALS_HANDLED="SIGHUP SIGINT SIGQUIT SIGTERM SIGXCPU SIGXFSZ"

# Globals
PID=

main()
{
    if [ $# -lt 1 ]; then
        usage
        exit ${EX_USAGE}
    fi

    handle_signals

    "$@" &

    PID=$!

    wait

    sleep 1

    kill_proc_tree "${PID}"

    return ${EX_OK}
}

handle_signals()
{
    trap '' ${SIGNALS_IGNORED}
    trap "_ERRLEVEL=\$?; cleanup; exit \${_ERRLEVEL}" EXIT
    trap "cleanup; exit 70" ${SIGNALS_HANDLED}
}

ignore_all_signals()
{
    trap '' ${SIGNALS_HANDLED} EXIT
}

restore_signals()
{
    trap - ${SIGNALS_HANDLED} ${SIGNALS_IGNORED} EXIT
}

cleanup()
{
    ignore_all_signals

    if [ -n "${PID}" ]; then
        kill_proc_tree "${PID}"
    fi

    restore_signals
}

usage()
{
    echo "usage: safe-exc.sh <cmd> [<args> ...]"
}

main "$@"
