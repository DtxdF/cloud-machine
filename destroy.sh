#!/bin/sh

BASEDIR=`dirname -- "$0"` || exit $?
BASEDIR=`realpath -- "${BASEDIR}"` || exit $?

. "${BASEDIR}/lib.subr"
. "${BASEDIR}/config.conf"

main()
{
    if [ $# -lt 1 ]; then
        usage
        exit ${EX_USAGE}
    fi

    local vm
    vm="$1"

    if [ -n "${VPN_NODE}" ]; then
        NODE_ID=`"${BASEDIR}/jq.sh" "${BASEDIR}/cluster/settings.json" -r '.["node-id"]'`
        VPN_PEER="peer://vm/${NODE_ID}/${vm}"

        if ssh -- "${VPN_NODE}" check "${VPN_PEER}"; then
            ssh -- "${VPN_NODE}" del "${VPN_PEER}" || exit $?
        fi
    fi

    local pid
    pid=`vm info "${vm}" | grep -m1 -Ee 'state: ' | sed -Ee 's/  state: running \(([0-9]+)\)/\1/' | tr -d ' '`

    if printf "%s" "${pid}" | grep -qEe '^[0-9]+$'; then
        vm stop "${vm}" || exit $?
        pwait -ot 60 ${pid}
        sleep 1
    fi

    vm destroy -f "${vm}" || exit $?

    sysrc "vm_list-=${vm}" || exit $?

    exit ${EX_OK}
}

usage()
{
    echo "destroy.sh <vm>"
}

main "$@"
