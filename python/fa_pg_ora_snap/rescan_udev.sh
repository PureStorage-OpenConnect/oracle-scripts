# rescan SCSI bus and check devices are present in /dev/oracleasm
# use this version when ASM devices are managed by UDEV rules
# add to sudoers for oracle
# oracle  ALL=(ALL:ALL) NOPASSWD: /root/udev/rescan_udev.sh

/usr/bin/rescan-scsi-bus.sh -r

ls /dev/oracleasm
