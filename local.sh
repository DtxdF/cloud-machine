#!/bin/sh

set -e

AUTH_KEY=
SSH_KEY=
TIMEZONE="UTC"
TIMEOUT=120

for opt in "$@"; do
    key=`printf "%s" "${opt}" | cut -d= -f1`
    
    if [ -z "${key}" ]; then
        echo "Invalid syntax -- <option>[=<argument>]"
        exit 1
    fi

    val=`printf "%s" "${opt}" | cut -d= -f2-`

    case "${key}" in
        ts_auth_key)
            AUTH_KEY="${val}"
            ;;
        ts_timeout)
            TIMEOUT="${val}"
            ;;
        ssh_pubkey)
            SSH_KEY="${val}"
            ;;
        timezone)
            TIMEZONE="${val}"
            ;;
    esac
done

if [ -z "${AUTH_KEY}" ]; then
    echo "Option requires an argument -- ts_auth_key"
    exit 1
fi

if [ -z "${SSH_KEY}" ]; then
    echo "Option requires an argument -- ssh_pubkey"
    exit 1
fi

set -x

appjail fetch
appjail network auto-create

echo "tmpfs /usr/local/appjail/cache/tmp/.appjail tmpfs rw,late 0 0" >> /etc/fstab

cat << EOF > /etc/rc.local
/usr/local/bin/tailscale up --auth-key="${AUTH_KEY}" && rm -f /etc/rc.local
EOF

echo "${SSH_KEY}" > /etc/ssh/authorized_keys

touch /var/tmp/appjail-hosts

ln -fs "/usr/share/zoneinfo/${TIMEZONE}" /etc/localtime
