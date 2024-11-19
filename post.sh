#!/bin/sh

set -ex

for releasedir in usr/local/appjail/releases/amd64/*/default/release; do
    releasedir=`realpath -- "${releasedir}"` || exit $?

    freebsd_version=`chroot "${releasedir}" freebsd-version | sed -Ee 's/\-p[0-9]+$//'` || exit $?

    env PAGER=cat freebsd-update \
        --not-running-from-cron \
        -b "${releasedir}" \
        --currently-running "${freebsd_version}" \
            fetch install
done
