#!/bin/sh

BASEDIR=`dirname -- "$0"` || exit $?
BASEDIR=`realpath -- "${BASEDIR}"` || exit $?

TAGS=
BLOCKSTORAGE=

. "${WRKDIR}/config.conf"

for opt in "$@"; do
    key=`printf "%s" "${opt}" | cut -d= -f1`
    
    if [ -z "${key}" ]; then
        echo "Invalid syntax -- <option>[=<argument>]"
        exit 1
    fi

    val=`printf "%s" "${opt}" | cut -d= -f2-`

    case "${key}" in
        tags)
            TAGS="${val}"
            ;;
        blockstorage)
            BLOCKSTORAGE="${val}"
            ;;
    esac
done

set -ex

freebsd_version=`chroot . freebsd-version | sed -Ee 's/\-p[0-9]+$//'` || exit $?

componentsdir="usr/local/appjail/cache/components/amd64/${freebsd_version}/default"

mkdir -p "${componentsdir}"

cp -a "${WRKDIR}/components/" "${componentsdir}"

if [ -n "${TAGS}" ]; then
    vm_bhyve_dir=`sysrc -ni vm_dir`

    if [ -z "${vm_bhyve_dir}" ]; then
        err "Could not get vm(1) directory!"
        exit 1
    fi

    cwd=`pwd` || exit $?
    vm_name=`basename "${cwd}"` || exit $?
    vm_dir="${vm_bhyve_dir}/${vm_name}"

    for tag in ${TAGS}; do
        printf "%s\n" "${tag}"
    done > "${vm_dir}/.tags" || exit $?
fi

if [ -n "${BLOCKSTORAGE}" ]; then
    vm add \
        -d disk \
        -t file \
        -s "${BLOCKSTORAGE}" \
            "${VMNAME}"
fi

if [ -n "${VPN_NODE}" ]; then
    NODE_ID=`"${BASEDIR}/jq.sh" "${WRKDIR}/cluster/settings.json" -r '.["node-id"]'`
    VPN_PEER="peer://vm/${NODE_ID}/${VMNAME}"

    if ! ssh -- "${VPN_NODE}" check "${VPN_PEER}"; then
        ssh -- "${VPN_NODE}" add "${VPN_PEER}"
    fi

    ssh -- "${VPN_NODE}" show "${VPN_PEER}" > usr/local/etc/wireguard/wg0.conf
    chmod 400 usr/local/etc/wireguard/wg0.conf
fi
