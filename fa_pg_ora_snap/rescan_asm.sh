# this code should be executable by the grid and or oracle users using sudo without a password
# use visudo to add this to the list of sudoers
export ORACLE_SID=+ASM
export ORAENV_ASK=NO
source /root/.bash_profile
export PATH=$PATH:/usr/local/bin
. /usr/local/bin/oraenv
asmcmd afd_refresh
asmcmd afd_lsdsk
