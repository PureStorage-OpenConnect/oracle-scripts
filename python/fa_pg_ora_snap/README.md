# Python scripts for snapshot and cloning an Oracle database on Pure Flash Array

The script fa_pg_ora_snap.py provides for taking a snapshot clone of an Oracle database using ASM, with volumes in a protection group on a Pure Flash Array.\
The code can also clone the source database to a target database server.  The code will check to determine of the target database and ASM diskgroups are offline before execution.  If they are still online, the code will refuse to execute.\
It will also optionally copy that snapshot to a target protection group.  In this case the target protection group must have an equal or greater number of volumes of equal or larger size than the source.\
The script can also copy an existing snapshot of a source protection group to a target protection group.\
If replication is set up for the source protection group, the snapshot can be replicated to a second Flash Array.

# Requirements:

This Python code imports the [fa_pg_snap.py](../fa_pg_snap/) code.

# Arguments:

-s source protection group (required)\
-t target protection group (optional)\
-n the snapshot name.  If this does not exist - it will create it.  If it already exists, it will use the existing snapshot to sync to the target. (required)\
-f JSON file with FQDN and API token to connect to the Flash Arrays (required)\
-r replicate the snapshot to the targets specified in the source protection group (optional)\
-o startup mode of the target database (OPEN, MOUNTED, STARTED or DOWN)\
-b use oracle backup mode (optional - defaults to no) 
-i ignore tag (optional - see below)\
-x execute lock - if this is NOT set, no destructive actions will be taken.  Instead, the script will simply tell you would it would do.  This may prove useful to make sure you have all the settings right before you  overwrite a target protection group.\
Note - many database parameters must be specified in the JSON file - see below:

# JSON file settings:

* rescan_scsi_bus - how to scan for new ASM disks (two examples are included in the repository)
* asm_sid - ASM SID on the target machine
* asm_home - ASM home on the target machine
* oracle_sid - Oracle SID of the cloned database (must exist on the target server)
* oracle_home - Oracle home on the target machine
* oracle_target_mode - requested state of cloned database (OPEN, DOWN, STARTED or MOUNTED) - overriden by the command line option
* local_listener - the listener the target database is to register with
* db_unique_name - the db_unique_name setting of the cloned database 
* ora_src_usr - source database user 
* ora_src_pwd - source database password 
* ora_src_cs - source database connection string
* ora_backup_mode - whether to use Oracle backup mode - overriden by command line option
    
# Notes:

When fully cloning a database from source to target, the code must execute on the target database server as a privileged user able to mount ASM diskgroups and start the target database.  This code assumes that the ASM Grid Infrastructure is owned by the same oracle user as the database.\
This code required password-less sudo privileges to execute the rescan_afd.sh script.\
If replication is not specified, both the source and target protection groups are assumed to be on the source Flash Array, and the target Flash Array is ignored.\
If the JSON file does not specify authentication credentials, the code will try to read the OS variables FA_HOST and API_TOKEN for authentication to the source Flash Array.\
If the JSON file does not specify authentication credentials, the code will try to read the OS variables FA_HOST_TGT and API_TOKEN_TGT for authentication to the target Flash Array.

# Tagging the database snapshot

The python code adds numerous tags to the database snapshot.  This allows the DBA to recover the database from the snapshot at a later time when, perhaps, the source database is no longer available to inspect.\
The tags include the database time the snapshot was made, which allows the use of the "recover database snapshot time" syntax.\
Tags also include the database ID, database name, if the database was in backup mode or not, and the location of the database controlfiles.

# A Worked Example

In the example below, the database SWINGPRD running on a different Linux server has its ASM diskgroups in a Pure Flash Array protection group called gct-oradb-demo-prd01-pg\
The code will snapshot that protection group, and then overwrite volumes on the local Linux server, where Oracle is also installed.  The code will then start the cloned ASM diskgroups, mount the cloned database and open it read-write.


```
[oracle@gct-oradb-demo-dev01 py]$ python fa_pg_ora_snap.py -f ora_prd01_2_dev01.json -n dec052338 -b -o open -x
============
fa_pg_ora_snap.py 1.9.0 started at 2025-12-05 23:38:03.169537
============
connecting to Flash Array:sn1-x90r2-f06-27.puretec.purestorage.com
connected
============
determining if snapshot dec052338 exists for source pg:gct-oradb-demo-prd01-pg
source protection group:gct-oradb-demo-prd01-pg
target protection group:gct-oradb-demo-dev01-pg
============
setting local oracle sid and home
============
connecting to source database:gct-oradb-demo-prd01:1521/SJC
use backup mode:True
============
reading source database settings
database name: SWINGDB
database id: 4017528888
database time: 2025/12/05 23:38:03
database unique name: SJC
database role: PRIMARY
archivelog mode: ARCHIVELOG
flashback mode: NO
encrypted tablespaces: 0
platform name: Linux x86 64-bit
version: Oracle Database 19c Enterprise Edition Release 19.0.0.0.0 - Production,Version 19.22.0.0.0
control_files: +DATA/SWINGDB/CONTROLFILE/current.266.1201708985, +FRA/SJC/CONTROLFILE/current.256.1218830433
db_recovery_file_dest: +FRA
db_recovery_file_dest_size: 34359738368
enable_pluggable_database: FALSE
============
source db begin backup mode
============
creating snapshot for gct-oradb-demo-prd01-pg
============
source db end backup mode
============
querying the volumes for protection group:gct-oradb-demo-prd01-pg
gct-oradb-demo-prd01-data-00
gct-oradb-demo-prd01-data-01
gct-oradb-demo-prd01-fra-00
gct-oradb-demo-prd01-fra-01
============
tagging the snapshot: key:db_name val:SWINGDB
tagging the snapshot: key:db_id val:4017528888
tagging the snapshot: key:db_time val:2025/12/05 23:38:03
tagging the snapshot: key:db_unique_name val:SJC
tagging the snapshot: key:db_role val:PRIMARY
tagging the snapshot: key:archivelog_mode val:ARCHIVELOG
tagging the snapshot: key:flashback_mode val:NO
tagging the snapshot: key:platform_name val:Linux x86 64-bit
tagging the snapshot: key:encrypted_tablespaces val:0
tagging the snapshot: key:version val:Oracle Database 19c Enterprise Edition Release 19.0.0.0.0 - Production,Version 19.22.0.0.0
tagging the snapshot: key:backup_mode val:Yes
tagging the snapshot: key:control_files val:+DATA/SWINGDB/CONTROLFILE/current.266.1201708985, +FRA/SJC/CONTROLFILE/current.256.1218830433
tagging the snapshot: key:db_recovery_file_dest val:+FRA
tagging the snapshot: key:db_recovery_file_dest_size val:34359738368
tagging the snapshot: key:enable_pluggable_database val:FALSE
tagging the snapshot: key:asm_disk_group val:DATA,FRA
============
excluded volumes
============
listing the volumes for snapshot:dec052338
name:gct-oradb-demo-prd01-pg.dec052338.gct-oradb-demo-prd01-data-00 size:120.0 GB
name:gct-oradb-demo-prd01-pg.dec052338.gct-oradb-demo-prd01-data-01 size:120.0 GB
name:gct-oradb-demo-prd01-pg.dec052338.gct-oradb-demo-prd01-fra-00 size:40.0 GB
name:gct-oradb-demo-prd01-pg.dec052338.gct-oradb-demo-prd01-fra-01 size:40.0 GB
============
determining if target instance swingdev is running
target instance is not running
============
determining if target ASM diskgroups are mounted
ASM diskgroup DATA is not mounted on target
ASM diskgroup FRA is not mounted on target
============
querying the volumes for protection group:gct-oradb-demo-dev01-pg
gct-oradb-demo-dev01-data-00
gct-oradb-demo-dev01-data-01
gct-oradb-demo-dev01-fra-00
gct-oradb-demo-dev01-fra-01
============
querying target volume details
name:gct-oradb-demo-dev01-data-00 id:a67641ac-9a36-c375-baf1-298c8a98ffe5 size:120.0
   is a target for gct-oradb-demo-prd01-pg.dec052338.gct-oradb-demo-prd01-data-00 size:120.0 GB
name:gct-oradb-demo-dev01-data-01 id:ee320b80-0bec-5a70-5032-87565859e10f size:120.0
   is a target for gct-oradb-demo-prd01-pg.dec052338.gct-oradb-demo-prd01-data-01 size:120.0 GB
name:gct-oradb-demo-dev01-fra-00 id:173bdf4e-5d71-c89d-8e00-9746337999da size:40.0
   is a target for gct-oradb-demo-prd01-pg.dec052338.gct-oradb-demo-prd01-fra-00 size:40.0 GB
name:gct-oradb-demo-dev01-fra-01 id:d2680577-4c5f-f094-0a92-98f01e85c7a8 size:40.0
   is a target for gct-oradb-demo-prd01-pg.dec052338.gct-oradb-demo-prd01-fra-01 size:40.0 GB
============
determining volume mapping
nm:gct-oradb-demo-prd01-pg.dec052338.gct-oradb-demo-prd01-data-00 src id:a5abc4c3-f199-c026-7c97-a2468e4b5fda map:0 sz:120.0
  checking for tag matched volume
    volume gct-oradb-demo-prd01-pg.dec052338.gct-oradb-demo-prd01-data-00 will be synced to gct-oradb-demo-dev01-data-00
nm:gct-oradb-demo-prd01-pg.dec052338.gct-oradb-demo-prd01-data-01 src id:6c2937de-c30e-dde0-9613-fb15a06966b3 map:0 sz:120.0
  checking for tag matched volume
    volume gct-oradb-demo-prd01-pg.dec052338.gct-oradb-demo-prd01-data-01 will be synced to gct-oradb-demo-dev01-data-01
nm:gct-oradb-demo-prd01-pg.dec052338.gct-oradb-demo-prd01-fra-00 src id:cbda1d30-1313-4b3e-df61-f1fa35957ac3 map:0 sz:40.0
  checking for tag matched volume
    volume gct-oradb-demo-prd01-pg.dec052338.gct-oradb-demo-prd01-fra-00 will be synced to gct-oradb-demo-dev01-fra-00
nm:gct-oradb-demo-prd01-pg.dec052338.gct-oradb-demo-prd01-fra-01 src id:feabf082-e2ce-aaa5-b1ea-8adfd586a7c4 map:0 sz:40.0
  checking for tag matched volume
    volume gct-oradb-demo-prd01-pg.dec052338.gct-oradb-demo-prd01-fra-01 will be synced to gct-oradb-demo-dev01-fra-01
============
mapping the volumes
gct-oradb-demo-prd01-pg.dec052338.gct-oradb-demo-prd01-data-00 will be syncd to gct-oradb-demo-dev01-data-00
gct-oradb-demo-prd01-pg.dec052338.gct-oradb-demo-prd01-data-01 will be syncd to gct-oradb-demo-dev01-data-01
gct-oradb-demo-prd01-pg.dec052338.gct-oradb-demo-prd01-fra-00 will be syncd to gct-oradb-demo-dev01-fra-00
gct-oradb-demo-prd01-pg.dec052338.gct-oradb-demo-prd01-fra-01 will be syncd to gct-oradb-demo-dev01-fra-01
============
The Oracle base has been set to /u01/app/oracle
--------------------------------------------------------------------------------
Label                     Filtering   Path
================================================================================
DATA00                     DISABLED   /dev/sde
DATA01                     DISABLED   /dev/sdf
FRA00                      DISABLED   /dev/sdb
FRA01                      DISABLED   /dev/sdd
GRID1                      DISABLED   /dev/sdc
============
mounting ASM diskgroups on target
mounting diskgroup DATA
mounting diskgroup FRA
ASM diskgroup DATA is mounted on the target
ASM diskgroup FRA is mounted on the target
all ASM diskgroups mounted on the target
============
requested state of swingdev is:OPEN
resetting the target SPFILE
alter system set db_name='SWINGDB' sid='*' scope=spfile;
alter system set control_files='+DATA/SWINGDB/CONTROLFILE/current.266.1201708985','+FRA/SJC/CONTROLFILE/current.256.1218830433' sid='*' scope=spfile;
alter system set db_recovery_file_dest='+FRA' sid='*' scope=spfile;
alter system set db_recovery_file_dest_size=34359738368 sid='*' scope=spfile;
alter system set enable_pluggable_database=FALSE sid='*' scope=spfile;
alter system set db_unique_name=swingdev sid='*' scope=spfile;
actual state of swingdev is:OPEN
============
complete
```
