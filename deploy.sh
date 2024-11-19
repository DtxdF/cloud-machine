#!/bin/sh

BASEDIR=`dirname -- "$0"` || exit $?
BASEDIR=`realpath -- "${BASEDIR}"` || exit $?

. "${BASEDIR}/lib.subr"

main()
{
    if [ $# -lt 1 ]; then
        usage
        exit ${EX_USAGE}
    fi

    local vm_bhyve_dir
    vm_bhyve_dir=`sysrc -ni vm_dir`

    if [ -z "${vm_bhyve_dir}" ]; then
        err "Could not get vm(1) directory!"
        exit ${EX_NOINPUT}
    fi

    local next_id
    next_id=1

    local vm_name=

    while :; do
        if [ ${next_id} -ge 999 ]; then
            err "The maximum allocation has been made."
            exit ${EX_NOPERM}
        fi

        local next_name
        next_name=`printf "vm%003d" "${next_id}"`

        if [ ! -d "${vm_bhyve_dir}/${next_name}" ]; then
            vm_name="${next_name}"
            break
        fi

        next_id=$((next_id+1))
    done

    local profile
    profile="$1"

    shift

    if [ ! -d "${BASEDIR}/dirty" ]; then
        mkdir -p "${BASEDIR}/dirty" || exit $?
    fi

    touch "${BASEDIR}/dirty/${vm_name}" || exit $?

    "${BASEDIR}/profiles/${profile}.sh" \
        "${vm_name}" "$@" || exit $?

    info "Starting VM '${vm_name}'"

    vm start "${vm_name}" || exit $?

    rm -f "${BASEDIR}/dirty/${vm_name}" || exit $?

    return ${EX_OK}
}

usage()
{
    echo "deploy.sh <profile-name> [<args> ...]"
}

main "$@"
