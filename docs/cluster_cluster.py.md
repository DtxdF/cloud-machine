The `cluster.py` script has some responsibilities. It is mainly executed by supervisord, when we talk about beanstalkd tubes (created by this script) like `create`, `forward` and `destroy`. But it can be used by the manager or a script or a program when we talk about subcommands like `create`, `destroy` and `logs`.

**create**:

`--tags` is a mandatory parameter, needed when we need to destroy a virtual machine or find one with the `find.sh` script. The virtual machines are called `vm001`, `vm002`, ..., `vm999`. This is intentional, of course, and allows us not to worry about the name we need. That is why tags are born. Tags allow us to use specific tags to identify specific virtual machines. There is no official meaning of how the tags should be used, but the mere convention is to use something like `<email>.<NNN> <email>`, where `<email>` is the user's email address and `<NNN>` is the length of virtual machine the user has. The reason for using these tags is that it allows the manager to destroy a specific uniquely identified virtual machine in the cluster (`<email>.<NNN>`) or to destroy all virtual machines of a user (`<email>`). For example, `user@gmail.com.012 user@gmail.com`.

`--options` depends entirely on the `pre.sh`, `local.sh` and `post.sh` scripts, so you should read them all to see which options are considered accepted, but the example below is sufficient to show the common use case.

```sh
../run.sh ./cluster.py create --options "ts_auth_key=tskey-auth-... timezone=America/Caracas \"ssh_pubkey=ssh-ed25519 ...\"" --tags "DtxdF@disroot.org DtxdF@disroot.org.001"
```

**destroy**:

This subcommand destroys all virtual machines that match the specified tag.

```sh
../run.sh ./cluster.py destroy --tags DtxdF@disroot.org
```

**logs**:

Displays in JSON format the logs as a sorted dictionary using the timestamp in UNIX format.

```sh
../run.sh ./cluster.py logs
```
