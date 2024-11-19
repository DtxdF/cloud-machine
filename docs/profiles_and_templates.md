Profiles are scripts that call the create.sh script with a specific template. Profiles are named in the same way as templates, for example, `CS0.sh` is the profile and `CS0.conf` is the template. In addition to using the template with the same name, profiles also define the size of the disk. Profiles also allow additional parameters to be passed to `create.sh`.

| Profile | Template | Disk Size | vCPU | Memory  |
| ------- | -------- | --------- | ---- | ------- |
| CS0     | CS0      | 20G       | 1    | 256 MiB |
| CS1     | CS1      | 30G       | 1    | 512 MiB |
| CS2     | CS2      | 40G       | 2    | 1 GiB   |
| CS3     | CS3      | 50G       | 2    | 2 GiB   |
| CS4     | CS4      | 60G       | 2    | 4 GiB   |
| CS5     | CS5      | 80G       | 4    | 8 GiB   |

**Note**: Templates must use `nvme` as disk type.
