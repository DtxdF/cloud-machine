#!/bin/sh

BASEDIR=`dirname -- "$0"` || exit $?
BASEDIR=`realpath -- "${BASEDIR}"` || exit $?

. "${BASEDIR}/config.conf"

vm switch create \
	-t manual \
	-b "${BRIDGE}" \
	"${SWITCH}"
