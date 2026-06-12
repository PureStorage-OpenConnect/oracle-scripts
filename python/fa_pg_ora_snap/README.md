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
- OS authentication to the local instances - the code connects with `connect / as sysdba` and `connect / as sysasm`
- This Python code imports the [fa_pg_snap.py](../fa_pg_snap/) code, which must be in the same directory or on the PYTHONPATH.

# Arguments:

-s source protection group (required unless `source_protection_group` or `src_protection_group` is set in the JSON config file)\
-t target protection group (optional - may also be set with `target_protection_group` or `tgt_protection_group` in the JSON config file)\
-n the snapshot name.  If this does not exist - it will create it.  If it already exists, it will use the existing snapshot to sync to the target, reading the database settings from the snapshot tags. (required)\
-f JSON file with FQDN and API token to connect to the Flash Arrays (required)\
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
If the JSON file does not specify authentication credentials, the code will try to read the OS variables FA_HOST and API_TOKEN for authentication to the source Flash Array.\
If the JSON file does not specify authentication credentials, the code will try to read the OS variables FA_HOST_TGT and API_TOKEN_TGT for authentication to the target Flash Array.

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
[oracle@gct-oradb-demo-tst01 py]$ python fa_pg_ora_snap.py -f json/prd01_2_tst01.local.json -n jun121237 -x -o open -b -r
============
fa_pg_ora_snap.py 1.9.0 started at 2026-06-12 12:37:15.474470
============
connecting to Flash Array:source_flash_array.localdomain API Version:2.44
connected
============
connecting to Flash Array:target_flash_array.localdomain API Version:2.44
connected
============
determining if snapshot jun121237 exists for protection group:gct-oradb-demo-prd01-pg
source protection group:gct-oradb-demo-prd01-pg
target protection group:gct-oradb-demo-tst01-pg
============
setting local oracle sid and home
============
connecting to source database:gct-oradb-demo-prd01:1521/SJC
use backup mode:True
============
reading source database settings
asm diskgroups: DATA,FRA
database name: SWINGDB
database id: 4017528888
database time: 2026/06/12 12:37:16
database open mode: READ WRITE
database role: PRIMARY
database threads: 1
encrypted tablespaces: 0
archivelog mode: ARCHIVELOG
flashback mode: NO
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
querying the volumes for protection group:gct-oradb-demo-prd01-pg on array source_flash_array
gct-oradb-demo-prd01-data-00
gct-oradb-demo-prd01-data-01
gct-oradb-demo-prd01-fra-00
gct-oradb-demo-prd01-fra-01
============
excluded volumes
============
listing the volumes for snapshot:jun121237
name:source_flash_array:gct-oradb-demo-prd01-pg.jun121237.gct-oradb-demo-prd01-data-00 sz:150.0 GB
name:source_flash_array:gct-oradb-demo-prd01-pg.jun121237.gct-oradb-demo-prd01-data-01 sz:150.0 GB
name:source_flash_array:gct-oradb-demo-prd01-pg.jun121237.gct-oradb-demo-prd01-fra-00 sz:40.0 GB
name:source_flash_array:gct-oradb-demo-prd01-pg.jun121237.gct-oradb-demo-prd01-fra-01 sz:40.0 GB
============
determining if target instance swingtst is running
target instance is not running
============
determining if target ASM diskgroups are mounted
ASM diskgroup DATA is not mounted on target
ASM diskgroup FRA is not mounted on target
============
querying the volumes for protection group:gct-oradb-demo-tst01-pg on array target_flash_array
gct-oradb-demo-tst01-data-00
gct-oradb-demo-tst01-data-01
gct-oradb-demo-tst01-fra-00
gct-oradb-demo-tst01-fra-01
============
querying target volume details
nm:gct-oradb-demo-tst01-data-00
  id:dd1b6dc5-78f1-a03c-dd4e-1f606a196909
  is a target for source_flash_array:gct-oradb-demo-prd01-pg.jun121237.gct-oradb-demo-prd01-data-00
  sz:150.0 GB
nm:gct-oradb-demo-tst01-data-01
  id:69fdd003-bf27-3768-3a0c-d1a0d10022c1
  is a target for source_flash_array:gct-oradb-demo-prd01-pg.jun121237.gct-oradb-demo-prd01-data-01
  sz:150.0 GB
nm:gct-oradb-demo-tst01-fra-00
  id:71c8587f-0250-659e-5ace-07d2cbea11e5
  is a target for source_flash_array:gct-oradb-demo-prd01-pg.jun121237.gct-oradb-demo-prd01-fra-00
  sz:40.0 GB
nm:gct-oradb-demo-tst01-fra-01
  id:68bff308-f1c6-a2ba-31f6-8bdbd574000d
  is a target for source_flash_array:gct-oradb-demo-prd01-pg.jun121237.gct-oradb-demo-prd01-fra-01
  sz:40.0 GB
============
determining volume mapping
nm:source_flash_array:gct-oradb-demo-prd01-pg.jun121237.gct-oradb-demo-prd01-data-00
  src id:eb6d1f1d-ffe9-2845-46fc-af9a65c36166 map:0
  sz:150.0 GB
  checking for tag matched volume
  will be synced to gct-oradb-demo-tst01-data-00
nm:source_flash_array:gct-oradb-demo-prd01-pg.jun121237.gct-oradb-demo-prd01-data-01
  src id:ee8c5202-be2e-90d3-aa4f-dd4d56a05dfd map:0
  sz:150.0 GB
  checking for tag matched volume
  will be synced to gct-oradb-demo-tst01-data-01
nm:source_flash_array:gct-oradb-demo-prd01-pg.jun121237.gct-oradb-demo-prd01-fra-00
  src id:e7d2d644-2b34-b551-5cc1-de87f8824525 map:0
  sz:40.0 GB
  checking for tag matched volume
  will be synced to gct-oradb-demo-tst01-fra-00
nm:source_flash_array:gct-oradb-demo-prd01-pg.jun121237.gct-oradb-demo-prd01-fra-01
  src id:3cd04a42-8511-b8cb-61e3-4284e417b1c3 map:0
  sz:40.0 GB
  checking for tag matched volume
  will be synced to gct-oradb-demo-tst01-fra-01
============
waiting on snapshot replication
...
replication complete
============
mapping the volumes
source_flash_array:gct-oradb-demo-prd01-pg.jun121237.gct-oradb-demo-prd01-data-00
  src key:eb6d1f1d-ffe9-2845-46fc-af9a65c36166
  map:dd1b6dc5-78f1-a03c-dd4e-1f606a196909
  will be syncd to gct-oradb-demo-tst01-data-00
source_flash_array:gct-oradb-demo-prd01-pg.jun121237.gct-oradb-demo-prd01-data-01
  src key:ee8c5202-be2e-90d3-aa4f-dd4d56a05dfd
  map:69fdd003-bf27-3768-3a0c-d1a0d10022c1
  will be syncd to gct-oradb-demo-tst01-data-01
source_flash_array:gct-oradb-demo-prd01-pg.jun121237.gct-oradb-demo-prd01-fra-00
  src key:e7d2d644-2b34-b551-5cc1-de87f8824525
  map:71c8587f-0250-659e-5ace-07d2cbea11e5
  will be syncd to gct-oradb-demo-tst01-fra-00
source_flash_array:gct-oradb-demo-prd01-pg.jun121237.gct-oradb-demo-prd01-fra-01
  src key:3cd04a42-8511-b8cb-61e3-4284e417b1c3
  map:68bff308-f1c6-a2ba-31f6-8bdbd574000d
  will be syncd to gct-oradb-demo-tst01-fra-01
============
The Oracle base has been set to /u01/app/oracle
--------------------------------------------------------------------------------
Label                     Filtering   Path
================================================================================
DATA00                     DISABLED   /dev/sdb
DATA01                     DISABLED   /dev/sdd
FRA00                      DISABLED   /dev/sde
FRA01                      DISABLED   /dev/sdf
GRID1                      DISABLED   /dev/sdc
============
mounting ASM diskgroups on target
mounting diskgroup DATA
mounting diskgroup FRA
ASM diskgroup DATA is mounted on the target
ASM diskgroup FRA is mounted on the target
all ASM diskgroups mounted on the target
============
requested state of swingtst is:OPEN
resetting the target SPFILE
alter system set db_name='SWINGDB' sid='*' scope=spfile;
alter system set control_files='+DATA/SWINGDB/CONTROLFILE/current.266.1201708985','+FRA/SJC/CONTROLFILE/current.256.1218830433' sid='*' scope=spfile;
alter system set db_recovery_file_dest='+FRA' sid='*' scope=spfile;
alter system set db_recovery_file_dest_size=34359738368 sid='*' scope=spfile;
alter system set enable_pluggable_database=FALSE sid='*' scope=spfile;
alter system set db_unique_name=swingtst sid='*' scope=spfile;
============
restarting instance
actual state of swingtst is:OPEN
============
complete

```
