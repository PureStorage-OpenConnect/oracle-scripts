#*******************************************************************************
# Script: clonedb.sh
# Author: Somu Rajarathinam (somu)
# Date  : 2016-08-19
#
# Purpose: Script for creating a clone of an Oracle DB on secondary server
# Works for single instance Oracle on filesystem on Linux
#
#*******************************************************************************
# Prerequisites:
# 1. The target volumes should have been discovered and mounted to target server
# 2. Target server to have the same Oracle binaries installed as that of source
# 3. Copy the init.ora file from source and make changes so it reflect target
# 4. Update the "puresnap" function with relevant volume information
#
# Note: Cloned database will have the same DB name as that of source, hence
# run this script on a secondary host and not on the source.
#
#*******Disclaimer:*************************************************************
# This script is offered "as is" with no warranty.  While this script is
# tested and worked in my environment, it is recommended that you test
# this script in a test lab before using in a production environment.
# No written permission needed to use this script but me or Pure Storage
# will not be liable for any damage or loss to the system.
#*******************************************************************************
#
#*******************************************************************************
# Update the following variables to the values relevant to your environment
# Begin user-updated configs
User="pureuser"      # Pure user on the FlashArray, pwd will be prompted
Array="purearray"    # Pure FlashArray, hostname or IP address
SrcPG="OraProdDbPG"  # Source Protection Group that contains data & redo
PFILE=/home/oracle/demo/demo1/initprod.ora
export ORACLE_SID=prod  # DB name
export ORACLE_HOME=/u01/app/oracle/product/12.1.0/dbhome_1
export PATH=$PATH:$ORACLE_HOME/bin
# End user-updated configs
#
#*******************************************************************************
# IMPORTANT
#   Please update the function puresnap with relevant source and volume details
#
#*******************************************************************************

function unmountfs() {
ct=$(ps -ef|grep -w ora_smon_$ORACLE_SID|grep -v grep)
if [ "${#ct}" -eq 0 ]; then

  #Replace the following with relevant mount details for your environment
  sudo umount /u02
  sudo umount /u03

else
  echo "Cannot unmount, check the usage on the mount !"
  exit -1
fi
}

function mountfs() {
#Replace the following with relevant mount details for your environment
sudo mount /u02
sudo mount /u03
}

function puresnap() {

# The snapshot will include the suffix of Unix epoch time
SUFFIX=`date +%s`
ssh ${User}@${Array} purepgroup snap --suffix DM1-$SUFFIX ${SrcPG}
echo "Copying data volume snapshot onto cloned data volume"
ssh ${User}@${Array} purevol copy --force ${SrcPG}.DM1-$SUFFIX.source_data_volume target_data_volume
echo "Copying redo volume snapshot onto cloned redo volume"
ssh ${User}@${Array} purevol copy --force ${SrcPG}.DM1-$SUFFIX.source_redo_volume target_redo_volume

# If you have more volumes, make sure to include them above in the same format
}

function startupDB() {

echo "startup pfile=$PFILE"
sqlplus / as sysdba << EOF
startup pfile=$PFILE
EOF

}

function shutdownDB() {

ct=$(ps -ef|grep -w ora_smon_$ORACLE_SID)
if [ "${#ct}" -gt 0 ]; then
    echo "Target DB is up.  Shutting it down!"
    sqlplus -s "/ as sysdba" << EOF
    shutdown abort;
    exit
EOF
fi
}


#clear
# Shutdown the target DB if it is up
shutdownDB

sdate=$(date +"%s")
echo "Unmounting filesystems...."
unmountfs

echo "Taking snapshot of $ORACLE_SID volumes"
puresnap

echo "Mounting filesystems ..."
mountfs

echo "Open the database in target server "
startupDB
edate=$(date +"%s")

ddiff=$(($edate-$sdate))
echo "Total Time: $(($ddiff / 60)) minutes and $(( $ddiff % 60 )) seconds"
