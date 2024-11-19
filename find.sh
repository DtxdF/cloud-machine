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

    local tags
    tags="$1"

    local vm_bhyve_dir
    vm_bhyve_dir=`sysrc -ni vm_dir`

    if [ -z "${vm_bhyve_dir}" ]; then
        err "Could not get vm(1) directory!"
        exit ${EX_NOINPUT}
    fi

    local pattern_file
    pattern_file=`mktemp`

    local tag
    for tag in ${tags}; do
        printf "%s\n" "${tag}"
    done > "${pattern_file}" || exit $?

    local next_id
    next_id=1

    while :; do
        if [ ${next_id} -ge 999 ]; then
            break
        fi

        local next_name
        next_name=`printf "vm%003d" "${next_id}"`

        local tags_file
        tags_file="${vm_bhyve_dir}/${next_name}/.tags"

        if [ -f "${tags_file}" ]; then
            if rg --pcre2 -qf "${pattern_file}" "${tags_file}"; then
                printf "%s\n" "${next_name}"
            fi
        fi

        next_id=$((next_id+1))
    done | sort | uniq

    rm -f "${pattern_file}"

    return ${EX_OK}
}

usage()
{
    echo "usage: find.sh <tags>"
}

main "$@"
