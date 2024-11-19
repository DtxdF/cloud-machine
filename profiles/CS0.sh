#!/bin/sh

BASEDIR=`dirname -- "$0"` || exit $?
BASEDIR=`realpath -- "${BASEDIR}"` || exit $?

main()
{
    "${BASEDIR}/../create.sh" \
        -t "CS0" \
        -s "20G" \
        "$@"
}

main "$@"
