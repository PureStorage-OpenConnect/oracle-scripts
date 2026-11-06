# Python scripts for snapshot and cloning an Oracle database on an Everpure Flash Array

The script fa_pg_ora_snap.py provides for taking a snapshot clone of an Oracle database using ASM, with volumes in a protection group on an Everpure Flash Array.\
The code can also clone the source database to a target database server.  The code will check whether the target database and ASM diskgroups are offline before execution.  If they are still online, the code will refuse to execute.\
It will also optionally copy that snapshot to a target protection group.  In this case the target protection group must have an equal or greater number of volumes of equal or larger size than the source.\
The script can also copy an existing snapshot of a source protection group to a target protection group.  In this case the database settings are read back from the tags on the snapshot.\
If replication is set up for the source protection group, the snapshot can be replicated to a second Flash Array.

This script must execute on the target database host and does NOT support RAC clustering.

# Requirements:

- Python 3.8 or later
- py-pure-client (`python -m pip install py-pure-client`)
- python-oracledb (`python -m pip install oracledb`)
- `python -m pip install 'setuptools<72.0.0'`
- SQL*Plus available at `$ORACLE_HOME/bin/sqlplus` on the target host
- The target database SID defined in the local /etc/oratab file
- OS authentication to the local instances - the code connects with `connect / as sysdba` and `connect / as sysasm`
- This Python code imports the [fa_pg_snap.py](../fa_pg_snap/) code, which must be in the same directory or on the PYTHONPATH.

# Arguments:

-s source protection group (required unless `source_protection_group` or `src_protection_group` is set in the JSON config file)\
-t target protection group (optional - may also be set with `target_protection_group` or `tgt_protection_group` in the JSON config file)\
-n the snapshot name.  If this does not exist - it will create it.  If it already exists, it will use the existing snapshot to sync to the target, reading the database settings from the snapshot tags. (required)\
-j JSON file with FQDN and API token to connect to the Flash Arrays (required)\
-r replicate the snapshot to the targets specified in the source protection group (optional)\
-o startup mode of the target database (OPEN, MOUNT, NOMOUNT or DOWN - case insensitive, defaults to DOWN)\
-b use oracle backup mode (optional - defaults to no)\
-i ignore tag (optional - see below)\
-x execute lock - if this is NOT set, no destructive actions will be taken.  Instead, the script will simply tell you what it would do.  This may prove useful to make sure you have all the settings right before you overwrite a target protection group.\
Note - many database parameters must be specified in the JSON file - see below:

# JSON file settings:

* src_flash_array_host - source flash array FQDN
* src_flash_array_api_token - source flash API token
* tgt_flash_array_host - target flash array FQDN (if using replication)
* tgt_flash_array_api_token - target flash API token (if using replication)
* flash_array_api_version - optional REST API version; auto-negotiated when omitted
* replicate - "True" to replicate the snapshot (the -r flag also enables this)
* source_protection_group (or src_protection_group) - the source protection group to be snapshot
* target_protection_group (or tgt_protection_group) - the target protection group to be sync'd to (optional)
* excluded_volumes - list of source volume IDs to exclude from the sync (optional)

* rescan_scsi_bus - how to scan for new ASM disks (three examples are included in the repository)
* asm_sid - ASM SID on the target machine (optional - ASM checks and mounts are skipped if asm_sid/asm_home are not set)
* asm_home - ASM home on the target machine
* oracle_sid - Oracle SID of the cloned database (required - must exist on the target server)
* oracle_home - Oracle home on the target machine (required)
* oracle_target_mode - requested state of cloned database (OPEN, MOUNT, NOMOUNT or DOWN) - overridden by the -o command line option
* local_listener - the listener the target database is to register with (optional)
* db_unique_name - the db_unique_name setting of the cloned database (optional)
* ora_src_usr - source database user (optional - see Notes)
* ora_src_pwd - source database password
* ora_src_cs - source database connection string
* ora_backup_mode - "True" to use Oracle backup mode (the -b flag also enables this)

# Notes:

When fully cloning a database from source to target, the code must execute on the target database server as a privileged user able to mount ASM diskgroups and start the target database.  This code assumes that the ASM Grid Infrastructure is owned by the same oracle user as the database.\
This code requires password-less sudo privileges to execute the rescan_afd.sh script.\
If ora_src_usr, ora_src_pwd and ora_src_cs are not all specified, the source database is not queried; database settings will only be available when syncing from an existing snapshot that carries them as tags.\
If replication is not specified, both the source and target protection groups are assumed to be on the source Flash Array, and the target Flash Array is ignored.\
If the JSON file does not specify authentication credentials, the code will try to read the OS variables PUREFA_URL and PUREFA_API for authentication to the source Flash Array.\
If the JSON file does not specify authentication credentials, the code will try to read the OS variables PUREFA_TARGET_URL and PUREFA_TARGET_API for authentication to the target Flash Array.

# Tagging the database snapshot

The python code adds numerous tags to the database snapshot.  This allows the DBA to recover the database from the snapshot at a later time when, perhaps, the source database is no longer available to inspect.\
The tags include the database time the snapshot was made, which allows the use of the "recover database snapshot time" syntax.\
Tags also include the database ID, database name, if the database was in backup mode or not, the location of the database controlfiles, the ASM diskgroups in use, and any open pluggable databases.\
A replicate tag records whether the snapshot was created with replication; if -r is used against an existing snapshot, this tag is checked and the script stops if the snapshot was not replicated when it was created.\
When an existing snapshot is used, these tags are read back and used to reset the SPFILE of the cloned database.

# A Worked Example

In the example below, the database SWINGPRD running on a different Linux server has its ASM diskgroups in an Everpure Flash Array protection group called gct-oradb-demo-prd01-pg\
The code will snapshot that protection group, and then overwrite volumes on the local Linux server, where Oracle is also installed.  The code will then start the cloned ASM diskgroups, mount the cloned database and open it read-write.\
(Output captured with an earlier version - message formatting differs slightly in the current version.)


```
[oracle@oradb-tst01 wip]$ python fa_pg_ora_snap.py -j json/prd01_2_tst01.local.json -n nov051736 -o open -b -r -x
============
fa_pg_ora_snap.py 2.0.0 started at 2026-11-05 15:36:31.695717
============
connecting to Flash Array:array01.example.com API Version:2.44
connected
============
connecting to Flash Array:array02.example.com API Version:2.44
connected
============
determining if snapshot nov051736 exists for protection group:oradb-prd01-pg
source protection group:oradb-prd01-pg
target protection group:oradb-tst01-pg
============
connecting to source database:oradb-prd01:1521/DEMOPRD
use backup mode:True
============
reading source database settings
asm diskgroups: FRA,DATA
database name: DEMODB
database id: 1000000002
database time: 2026/11/05 15:36:32
database open mode: READ WRITE
database role: PRIMARY
database threads: 1
encrypted tablespaces: 0
archivelog mode: ARCHIVELOG
flashback mode: NO
platform name: Linux x86 64-bit
version: Oracle Database 19c Enterprise Edition Release 19.0.0.0.0 - Production,Version 19.22.0.0.0
control_files: +DATA/DEMODB/CONTROLFILE/current.266.1201708985, +FRA/DEMOPRD/CONTROLFILE/current.256.1218830433
db_recovery_file_dest: +FRA
db_recovery_file_dest_size: 34359738368
enable_pluggable_database: FALSE
============
source db begin backup mode
============
creating snapshot for oradb-prd01-pg
============
source db end backup mode
============
querying the volumes for protection group:oradb-prd01-pg on array array01
oradb-prd01-data-00
oradb-prd01-data-01
oradb-prd01-fra-00
oradb-prd01-fra-01
============
excluded volumes
============
listing the volumes for snapshot:nov051736
name:array01:oradb-prd01-pg.nov051736.oradb-prd01-data-00 sz:150.0 GB
name:array01:oradb-prd01-pg.nov051736.oradb-prd01-data-01 sz:150.0 GB
name:array01:oradb-prd01-pg.nov051736.oradb-prd01-fra-00 sz:40.0 GB
name:array01:oradb-prd01-pg.nov051736.oradb-prd01-fra-01 sz:40.0 GB
============
setting local oracle home and sid variables
============
determining if target instance demotst is running
using oracle home:/u01/app/oracle/product/19.0.0/dbhome_1
target instance is not running
============
determining if target ASM diskgroups are mounted
using ASM instance +ASM with grid home:/u01/app/grid/19c
ASM diskgroup FRA is not mounted on target
ASM diskgroup DATA is not mounted on target
============
querying the volumes for protection group:oradb-tst01-pg on array array02
oradb-tst01-data-00
oradb-tst01-data-01
oradb-tst01-fra-00
oradb-tst01-fra-01
============
querying target volume details
nm:oradb-tst01-data-00
  id:bbbbbbbb-0000-0000-0000-000000000008
  is a target for array01:oradb-prd01-pg.nov051736.oradb-prd01-data-00
  sz:150.0 GB
nm:oradb-tst01-data-01
  id:bbbbbbbb-0000-0000-0000-000000000009
  is a target for array01:oradb-prd01-pg.nov051736.oradb-prd01-data-01
  sz:150.0 GB
nm:oradb-tst01-fra-00
  id:bbbbbbbb-0000-0000-0000-000000000010
  is a target for array01:oradb-prd01-pg.nov051736.oradb-prd01-fra-00
  sz:40.0 GB
nm:oradb-tst01-fra-01
  id:bbbbbbbb-0000-0000-0000-000000000011
  is a target for array01:oradb-prd01-pg.nov051736.oradb-prd01-fra-01
  sz:40.0 GB
============
determining volume mapping
nm:array01:oradb-prd01-pg.nov051736.oradb-prd01-data-00
  src id:bbbbbbbb-0000-0000-0000-000000000012 map:0
  sz:150.0 GB
  checking for tag matched volume
  will be synced to oradb-tst01-data-00
nm:array01:oradb-prd01-pg.nov051736.oradb-prd01-data-01
  src id:bbbbbbbb-0000-0000-0000-000000000013 map:0
  sz:150.0 GB
  checking for tag matched volume
  will be synced to oradb-tst01-data-01
nm:array01:oradb-prd01-pg.nov051736.oradb-prd01-fra-00
  src id:bbbbbbbb-0000-0000-0000-000000000014 map:0
  sz:40.0 GB
  checking for tag matched volume
  will be synced to oradb-tst01-fra-00
nm:array01:oradb-prd01-pg.nov051736.oradb-prd01-fra-01
  src id:bbbbbbbb-0000-0000-0000-000000000015 map:0
  sz:40.0 GB
  checking for tag matched volume
  will be synced to oradb-tst01-fra-01
============
waiting on snapshot replication
...
replication complete
============
mapping the volumes
array01:oradb-prd01-pg.nov051736.oradb-prd01-data-00
  src key:bbbbbbbb-0000-0000-0000-000000000012
  map:bbbbbbbb-0000-0000-0000-000000000008
  will be syncd to oradb-tst01-data-00
array01:oradb-prd01-pg.nov051736.oradb-prd01-data-01
  src key:bbbbbbbb-0000-0000-0000-000000000013
  map:bbbbbbbb-0000-0000-0000-000000000009
  will be syncd to oradb-tst01-data-01
array01:oradb-prd01-pg.nov051736.oradb-prd01-fra-00
  src key:bbbbbbbb-0000-0000-0000-000000000014
  map:bbbbbbbb-0000-0000-0000-000000000010
  will be syncd to oradb-tst01-fra-00
array01:oradb-prd01-pg.nov051736.oradb-prd01-fra-01
  src key:bbbbbbbb-0000-0000-0000-000000000015
  map:bbbbbbbb-0000-0000-0000-000000000011
  will be syncd to oradb-tst01-fra-01
============
The Oracle base has been set to /u01/app/oracle
--------------------------------------------------------------------------------
Label                     Filtering   Path
================================================================================
DATA00                     DISABLED   /dev/sdc
DATA01                     DISABLED   /dev/sdd
FRA00                      DISABLED   /dev/sde
FRA01                      DISABLED   /dev/sdf
GRID1                      DISABLED   /dev/sdb
============
mounting ASM diskgroups on target
mounting diskgroup FRA
mounting diskgroup DATA
ASM diskgroup FRA is mounted on the target
ASM diskgroup DATA is mounted on the target
all ASM diskgroups mounted on the target
============
requested state of demotst is:OPEN
resetting the target SPFILE
alter system set db_name='DEMODB' sid='*' scope=spfile;
alter system set control_files='+DATA/DEMODB/CONTROLFILE/current.266.1201708985','+FRA/DEMOPRD/CONTROLFILE/current.256.1218830433' sid='*' scope=spfile;
alter system set db_recovery_file_dest='+FRA' sid='*' scope=spfile;
alter system set db_recovery_file_dest_size=34359738368 sid='*' scope=spfile;
alter system set enable_pluggable_database=FALSE sid='*' scope=spfile;
alter system set db_unique_name=demotst sid='*' scope=spfile;
============
restarting instance
actual state of demotst is:OPEN
============
complete


```
