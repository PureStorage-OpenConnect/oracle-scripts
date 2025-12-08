# rescan for ASM devices and list ASM disks
# use this version with ASM Filter Drivers are used
# add to sudoers for oracle
# oracle  ALL=(ALL:ALL) NOPASSWD: /root/udev/rescan_afd.sh

export ORACLE_SID=+ASM
export ORAENV_ASK=NO
source /root/.bash_profile
export PATH=$PATH:/usr/local/bin
. /usr/local/bin/oraenv
asmcmd afd_refresh
asmcmd afd_lsdsk
