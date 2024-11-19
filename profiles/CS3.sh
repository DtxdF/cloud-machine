#!/bin/sh

BASEDIR=`dirname -- "$0"` || exit $?
BASEDIR=`realpath -- "${BASEDIR}"` || exit $?

main()
{
    "${BASEDIR}/../create.sh" \
        -t "CS3" \
        -s "50G" \
        "$@"
}

main "$@"
