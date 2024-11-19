#!/bin/sh

BASEDIR=`dirname -- "$0"` || exit $?
BASEDIR=`realpath -- "${BASEDIR}"` || exit $?

main()
{
    "${BASEDIR}/../create.sh" \
        -t "CS4" \
        -s "60G" \
        "$@"
}

main "$@"
