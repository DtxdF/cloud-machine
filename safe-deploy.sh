#!/bin/sh

BASEDIR=`dirname -- "$0"` || exit $?
BASEDIR=`realpath -- "${BASEDIR}"` || exit $?

set -T

main()
{
    lockf -k "${BASEDIR}/.lock" \
        "${BASEDIR}/deploy.sh" "$@"
}

main "$@"
