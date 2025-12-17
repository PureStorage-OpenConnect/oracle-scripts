#!/bin/sh

# generate UDEV rules for Purity devices suitable for ASM

dev_list=$(ls -1 /dev/sd* )
#dev_list=$(ls -1 /dev/sd?1 )
#dev_list=$(ls -1 /dev/mapper )

owner=oracle
group=dba
diskname=disk
base=0

#
# process command line arguments
#

if ( ! getopts "b:d:g:l:o:" opt); then
        echo "Usage: `basename $0` options (-d diskname) (-g group) (-l device_list) (-o owner)";
        exit $E_OPTERROR;
fi

while getopts "b:d:g:l:o:" opt; do
     case $opt in
         b) base=$OPTARG;;
         d) diskname=$OPTARG;;
         g) group=$OPTARG;;
         l) device_list=$OPTARG;;
         o) owner=$OPTARG;;
     esac
done

let i=$base

for dev in ${dev_list}
do
  basedev=`echo $dev | cut -f3 -d"/"`
##  echo "considering device $basedev"
  if [[ ",$device_list," = *",$basedev,"* ]] || [[ ${#device_list} -lt 1 ]]
  then
    myscid=`/usr/lib/udev/scsi_id -g -u -d /dev/$basedev`
    printf "KERNEL==\"sd*\", SUBSYSTEM==\"block\", ENV{ID_SERIAL}==\"%s\", SYMLINK+=\"oracleasm/$diskname%02d\", OPTIONS=\"nowatch\", OWNER=\"$owner\", GROUP=\"$group\", MODE=\"0660\"\n" ${myscid} $i

    let i=i+1
  fi
done
