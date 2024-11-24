#!/bin/sh

BASEDIR=`dirname -- "$0"` || exit $?
BASEDIR=`realpath -- "${BASEDIR}"` || exit $?

main()
{
    if [ $# -lt 1 ]; then
        usage
        exit ${EX_USAGE}
    fi

    local file
    file="$1"

    shift

    cat -- "${file}" | "${BASEDIR}/parse-json.py" | jq "$@"

    return ${EX_OK}
}

usage()
{
    echo "jq.sh <file> [<args> ...]"
}

main "$@"
