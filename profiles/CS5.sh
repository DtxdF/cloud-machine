#!/bin/sh

BASEDIR=`dirname -- "$0"` || exit $?
BASEDIR=`realpath -- "${BASEDIR}"` || exit $?

main()
{
    "${BASEDIR}/../create.sh" \
        -t "CS5" \
        -s "80G" \
        "$@"
}

main "$@"
