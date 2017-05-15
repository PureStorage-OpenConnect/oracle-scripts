######################################################################################################
# Disclaimer:
# For educational purposes only - no warranty is provided
# Test thoroughly - use at your own risk
#
# Script: repSnap.sh
# Author: Somu Rajarathinam
# Date: 07/21/2016
#
# Purpose: Script to refresh (overwrite) the target protection group with the latest snapshot from
# the source protection group
#
# The script runs connecting to the target or the replicated array, looks for the source PG that is
# being replicated, checks for the latest snapshot and when found overwrites the target PG
#
#
# Prerequisites
# 1) A target protection group with target volumes in the same order as that of source volumes.
#
# For safety reason, the overwrite command is commented out in this script and replaced with echo.
# When validated, uncomment the line with purevol copy --force
#
######################################################################################################
# Change the following section with your environment details

# Source PG - One that is being replicated 
sPG="pure-m50-2-ct0-b12-35:slobDbPG"

# Target PG - This should include the list of target volumes on to which the snapshot will be copied
tPG="devdbPG"

# The user to connect to the Pure Array.
pUser="pureuser"
# Note: Please setup public key if you do not want password prompt

# Target FlashArray where the replication lands (hostname or IP address)
destflashArray="csg-420-osboot"
######################################################################################################

#Set IFS to newline so array entry will have records that ends with newline
IFS=$'\n'
snaps=( $(ssh $pUser@$destflashArray purepgroup list --snap --transfer $sPG --csv) )
found=0
IFS=$','
flds=(${snaps[0]})
for ((i=0; i <${#flds[@]}; i++))
do
  if [ ${flds[$i]} == "Progress" ]
  then
    key=$i
    break
  fi
done
for ((i=1; i< ${#snaps[@]}; i++))
do
  IFS=$','
  rec=(${snaps[$i]})
  snapName=${rec[0]}
  progress=${rec[$key]}
  if [ "$progress" == "1.0" ]
  then
    found=1
    break
  fi
done

if [ "$found" -eq 1 ]
then
  IFS=$'\n'
  svols=( $(ssh $pUser@$destflashArray purevol list --snap --pgrouplist $snapName --notitle --csv) )
  dvols=( $(ssh $pUser@$destflashArray purepgroup listobj --type vol $tPG) )
  if [ ${#svols[@]} -eq ${#dvols[@]} ]
  then
    for ((i=0; i < ${#svols[@]}; i++))
    do
      svolName=`echo ${svols[$i]} |cut -d "," -f1`
      dvolName=`echo ${dvols[$i]} |cut -d "," -f1`
# Validate the output of the following command.
# If it shows the right source and target volumes,
# you can comment the following line with echo and uncomment the line with ssh
      echo "ssh $pUser@$destflashArray purevol copy --force $svolName $dvolName"
#     ssh $pUser@$destflashArray purevol copy --force $svolName $dvolName
#  Uncomment the above line when validated and ready to perform the actual volume overwrite
    done
   else
     echo "The source and target volumes don't match.  Please check the pgroup information"
   fi
else
  echo "No completed snapshots of $sPG available for cloning"
fi
