#!/bin/sh

BASEDIR=`dirname -- "$0"` || exit $?
BASEDIR=`realpath -- "${BASEDIR}"` || exit $?

main()
{
    "${BASEDIR}/../create.sh" \
        -t "CS2" \
        -s "40G" \
        "$@"
}

main "$@"
