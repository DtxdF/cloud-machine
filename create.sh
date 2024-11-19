#!/bin/sh

BASEDIR=`dirname -- "$0"` || exit $?
BASEDIR=`realpath -- "${BASEDIR}"` || exit $?

. "${BASEDIR}/lib.subr"
. "${BASEDIR}/config.conf"

# Global
GLOBAL_VM_NAME=
GLOBAL_VM_DIR=
GLOBAL_MD_DEVICE=
GLOBAL_VM_MNTDIR=
GLOBAL_VM_MNTDIR_MOUNTED=false
GLOBAL_ERROR=true

# Signals
SIGNALS_IGNORED="SIGALRM SIGVTALRM SIGPROF SIGUSR1 SIGUSR2"
SIGNALS_HANDLED="SIGHUP SIGINT SIGQUIT SIGTERM SIGXCPU SIGXFSZ"

main()
{
    local _o
    # options
    local components="${COMPONENTS:-base.txz kernel.txz}"
    local domain="${DOMAIN:-.lan}"
    local pre_script="${PRE_SCRIPT:-${BASEDIR}/pre.sh}"
    local post_script="${POST_SCRIPT:-${BASEDIR}/post.sh}"
    local mntdir="${MNTDIR:-/mnt}"
    local template="${TEMPLATE:-CS0}"
    local size="${SIZE:-20G}"
    local swap="${SWAP:-4G}"
    local chroot_script="${CHROOT_SCRIPT:-${BASEDIR}/local.sh}"
    local resolv_Conf="${RESOLV_CONF:-/etc/resolv.conf}"

    handle_signals

    local vm_bhyve_dir
    vm_bhyve_dir=`sysrc -ni vm_dir`

    if [ -z "${vm_bhyve_dir}" ]; then
        err "Could not get vm(1) directory!"
        exit ${EX_NOINPUT}
    fi

    while getopts ":c:C:d:m:p:P:r:s:S:t:" _o; do
        case "${_o}" in
            c)
                components="${OPTARG}"
                ;;
            C)
                chroot_script="${OPTARG}"
                ;;
            d)
                domain="${OPTARG}"
                ;;
            m)
                mntdir="${OPTARG}"
                ;;
            p)
                pre_script="${OPTARG}"
                ;;
            P)
                post_script="${OPTARG}"
                ;;
            r)
                resolv_conf="${OPTARG}"
                ;;
            s)
                size="${OPTARG}"
                ;;
            S)
                swap="${OPTARG}"
                ;;
            t)
                template="${OPTARG}"
                ;;
            *)
                usage
                exit ${EX_USAGE}
                ;;
        esac
    done
    shift $((OPTIND-1))

    if [ $# -lt 1 ]; then
        usage
        exit ${EX_USAGE}
    fi

    local name
    name="$1"
    
    shift

    swap=`tobytes "${swap}"`
    size=`tobytes "${size}"`
    
    local pad
    pad=`tobytes 8m`

    local rootpart_size
    rootpart_size=$((size-swap))

    info "Creating VM '${name}'"

    local vm_dir
    vm_dir="${vm_bhyve_dir}/${name}"

    GLOBAL_VM_DIR="${vm_dir}"
    GLOBAL_VM_NAME="${name}"

    vm create \
        -t "${template}" \
        -s $((size+pad)) \
            "${name}" || exit $?

    local vm_disk0
    vm_disk0="${vm_dir}/disk0.img"

    local md_device
    md_device=`mdconfig -at vnode -f "${vm_disk0}"` || exit $?

    GLOBAL_MD_DEVICE="${md_device}"

    info "md(4) device is '${md_device}'"

    info "Partitioning"

    gpart create -s gpt "${md_device}" || exit $?
    gpart add -a 1m -t freebsd-boot -s 512k "${md_device}" || exit $?
    gpart add -a 1m -t freebsd-swap -s "${swap}b" "${md_device}" || exit $?
    gpart add -a 1m -t freebsd-ufs -s "${rootpart_size}b" "${md_device}" || exit $?
    gpart bootcode -b /boot/pmbr -p /boot/gptboot -i 1 "${md_device}" || exit $?

    local rootpart
    rootpart="/dev/${md_device}p3"

    info "Formatting"

    newfs -U "${rootpart}" || exit $?

    local vm_mntdir
    vm_mntdir="${mntdir}/${name}"

    GLOBAL_VM_MNTDIR="${vm_mntdir}"

    mkdir -p "${vm_mntdir}" || exit $?

    info "Mounting ${rootpart} in ${vm_mntdir}"

    mount "${rootpart}" "${vm_mntdir}" || exit $?

    GLOBAL_VM_MNTDIR_MOUNTED=true

    local component
    for component in ${components}; do
        info "Extracting component '${component}'"

        local component_file
        component_file="${BASEDIR}/components/${component}"

        if [ ! -f "${component_file}" ]; then
            err "Component '${component}' cannot be found"
            exit ${EX_NOINPUT}
        fi

        tar -C "${vm_mntdir}" -xf "${component_file}" || exit $?
    done

    info "Writing fstab(5)"

    cat << "EOF" > "${vm_mntdir}/etc/fstab"
/dev/nda0p3        /           ufs         rw        1        1
/dev/nda0p2        none        swap        sw        0        0
EOF

    if [ -d "${BASEDIR}/files" ]; then
        info "Copying ${BASEDIR}/files/ to ${vm_mntdir}"

        cp -va "${BASEDIR}/files/" "${vm_mntdir}" || exit $?
    fi

    if [ -f "${vm_mntdir}/etc/resolv.conf" ]; then
        info "Backing up chroot's resolv.conf(5) file"

        cp -a "${vm_mntdir}/etc/resolv.conf" "${vm_mntdir}/etc/resolv.conf.bak" || exit $?
    fi

    info "Removing chroot's resolv.conf(5) file"

    chflags 0 "${vm_mntdir}/etc/resolv.conf" || exit $?
    rm -f "${vm_mntdir}/etc/resolv.conf" || exit $?

    if [ -f "${resolv_conf}" ]; then
        info "Copying '${resolv_Conf}' as the resolv.conf(5) file"

        cp -a "${resolv_conf}" "${vm_mntdir}/etc/resolv.conf" || exit $?
    else
        warn "resolv.conf(5) '${resolv_conf}' not found, using OpenDNS nameservers"

        printf "nameserver %s\nnameserver %s\n" \
            "208.67.222.222" "208.67.220.220" > "${vm_mntdir}/etc/resolv.conf" || exit $?
    fi

    if [ -f "${BASEDIR}/pkg.lst" ]; then
        info "Installing packages"

        pkg -c "${vm_mntdir}" install -y -- `cat "${BASEDIR}/pkg.lst"` || exit $?
    fi

    info "Configuring hostname"

    echo >> "${vm_mntdir}/etc/rc.conf"
    echo "# HOSTNAME" >> "${vm_mntdir}/etc/rc.conf"
    sysrc -R "${vm_mntdir}" hostname="${name}${domain}" || exit $?

    if [ -x "${pre_script}" ]; then
        info "Executing ${pre_script}"

        (cd "${vm_mntdir}"; VMNAME="${name}" WRKDIR="${BASEDIR}" "${pre_script}" "$@") || exit $?
    fi

    if [ -x "${chroot_script}" ]; then
        info "Copying ${chroot_script} as ${vm_mntdir}/local.sh"

        cp -va "${chroot_script}" "${vm_mntdir}/local.sh" || exit $?

        info "Executing local.sh"
        
        chroot "${vm_mntdir}" /local.sh "$@" || exit $?
        chroot "${vm_mntdir}" rm -f /local.sh || exit $?
    fi

    local freebsd_version
    freebsd_version=`chroot "${vm_mntdir}" freebsd-version | sed -Ee 's/\-p[0-9]+$//'` || exit $?

    info "Updating"

    env PAGER=cat freebsd-update \
        --not-running-from-cron \
        -b "${vm_mntdir}" \
        --currently-running "${freebsd_version}" \
            fetch install || exit $?

    if [ -x "${post_script}" ]; then
        info "Executing ${post_script}"

        (cd "${vm_mntdir}"; VMNAME="${name}" WRKDIR="${BASEDIR}" "${post_script}" "$@") || exit $?
    fi

    if [ -f "${vm_mntdir}/etc/resolv.conf.bak" ]; then
        info "Restoring previous resolv.conf(5) file"

        chflags 0 "${vm_mntdir}/etc/resolv.conf" || exit $?
        rm -f "${vm_mntdir}/etc/resolv.conf" || exit $?
        cp -a "${vm_mntdir}/etc/resolv.conf.bak" "${vm_mntdir}/etc/resolv.conf" || exit $?
        chflags 0 "${vm_mntdir}/etc/resolv.conf.bak" || exit $?
        rm -f "${vm_mntdir}/etc/resolv.conf.bak" || exit $?
    fi

    umount "${vm_mntdir}" || exit $?

    GLOBAL_VM_MNTDIR_MOUNTED=false

    rmdir "${vm_mntdir}" || exit $?

    info "Destroying md(4) device"

    mdconfig -du "${md_device}" || exit $?

    info "VM '${name}' will be started using 'vm startall' or 'vm start ${name}'"

    sysrc vm_list+="${name}" || exit $?

    GLOBAL_ERROR=false

    return ${EX_OK}
}

handle_signals()
{
    trap '' ${SIGNALS_IGNORED}
    trap "_ERRLEVEL=\$?; cleanup; exit \${_ERRLEVEL}" EXIT
    trap "cleanup; exit 70" ${SIGNALS_HANDLED}
}

ignore_all_signals()
{
    trap '' ${SIGNALS_HANDLED} EXIT
}

restore_signals()
{
    trap - ${SIGNALS_HANDLED} ${SIGNALS_IGNORED} EXIT
}

cleanup()
{
    ignore_all_signals

    if ! ${GLOBAL_ERROR}; then
        restore_signals
        return 0
    fi

    info "Cleaning up"

    if [ -n "${GLOBAL_VM_MNTDIR}" ] && [ -d "${GLOBAL_VM_MNTDIR}" ]; then
        if ${GLOBAL_VM_MNTDIR_MOUNTED}; then
            umount -f "${GLOBAL_VM_MNTDIR}"
        fi

        rmdir "${GLOBAL_VM_MNTDIR}"
    fi

    if [ -n "${GLOBAL_MD_DEVICE}" ] && [ -c "/dev/${GLOBAL_MD_DEVICE}" ]; then
        mdconfig -du "${GLOBAL_MD_DEVICE}"
    fi

    if [ -n "${GLOBAL_VM_DIR}" ] && [ -d "${GLOBAL_VM_DIR}" ]; then
        vm destroy -f "${GLOBAL_VM_NAME}"
    fi

    restore_signals
}

usage()
{
    echo "create.sh [-c <components>] [-C <script>] [-d <domain>] [-p <script>]"
    echo "          [-P <script>] [-m <mount-directory>] [-r <file>] [-s <size>]"
    echo "          [-S <swap-size>] [-t <template>] <name>"
}

main "$@"
