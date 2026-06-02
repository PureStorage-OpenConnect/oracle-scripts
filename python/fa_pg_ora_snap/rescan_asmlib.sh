# rescan SCSI bus and check devices are present in /dev/oracleasm
# use this version when ASM devices are managed by ASMLib rules
# add to sudoers for oracle
# oracle  ALL=(ALL:ALL) NOPASSWD: /root/udev/rescan_asmlib.sh

/usr/bin/rescan-scsi-bus.sh -r

oracleasm scandisks
oracleasm listdisks

