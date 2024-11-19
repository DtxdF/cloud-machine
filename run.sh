#!/bin/sh

PATH="${PATH}:/usr/local/bin:/usr/local/sbin"; export PATH

BASEDIR=`dirname -- "$0"` || exit $?
BASEDIR=`realpath -- "${BASEDIR}"` || exit $?

. "${BASEDIR}/env/bin/activate"
. "${BASEDIR}/lib.subr"

"$@"
