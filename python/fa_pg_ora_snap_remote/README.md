# Python scripts for snapshot and cloning an Oracle database on Pure Flash Array on remote servers

The script fa_pg_ora_snap_remote.py provides for taking a snapshot clone of an Oracle database using ASM, with volumes in a protection group on a Pure Flash Array.\
The code can also clone the source database to a target database server.  The code will check to determine of the target database and ASM diskgroups are offline before execution.  If they are still online, the code will refuse to execute.\
It will also optionally copy that snapshot to a target protection group.  In this case the target protection group must have an equal or greater number of volumes of equal or larger size than the source.\
The script can also copy an existing snapshot of a source protection group to a target protection group.\
If replication is set up for the source protection group, the snapshot can be replicated to a second Flash Array.

# Requirements:

This Python code imports the [fa_pg_snap.py](../fa_pg_snap/) code.
This Python code imports the [fa_pg_ora_snap.py](../fa_pg_ora_snap/) code.

# Arguments:

-f configuration JSON (required)\
-s source protection group (required)\
-t target protection group (optional)\
-n the snapshot name.  If this does not exist - it will create it.  If it already exists, it will use the existing snapshot to sync to the target. (required)\
-f JSON file with FQDN and API token to connect to the Flash Arrays (required)\
-r replicate the snapshot to the targets specified in the source protection group (optional)\
-o startup mode of the target database (OPEN, MOUNTED, STARTED or DOWN)\
-b use oracle backup mode (optional - defaults to no) 
-i ignore tag (override established source/target volume pairing for cloning - see fa_pg_ora_snap.py for more details)\
-x execute lock - if this is NOT set, no destructive actions will be taken.  Instead, the script will simply tell you would it would do.  This may prove useful to make sure you have all the settings right before you  overwrite a target protection group.\
Note - many database parameters must be specified in the JSON file - see below:

# JSON file settings:

* src_flash_array_host - FQDN of the source Pure Flash Array (required).
* src_flash_array_api_token - API token to authenticate against the source Pure Flash Array (required).
* tgt_flash_array_host - FQDN of the target Pure Flash Array (optional - if replicating).
* tgt_flash_array_api_token - API token to authenticate against the target Pure Flash Array (optional - if replicating).
* src_protection_group - Pure Flash Array protection group that includes all ASM disks in the source database (required).
* tgt_protection_group - Pure Flash Array protection group that includes all ASM disks in the target database (optional - if cloning database).
* rescan_scsi_bus - how to scan for new ASM disks (two examples are included in the repository)
* oracle_target_mode - requested state of cloned database (OPEN, DOWN, STARTED or MOUNTED) - overriden by the command line option

* def_user_oracle - default oracle username is no other provided
* def_passwd_oracle - default oracle password is no other provided
* def_user_grid - default grid username is no other provide.  defaults to oracle
* def_passwd_grid - default grid password is no other provide.
* def_asm - default ASM instance on the target host
* def_port - default ssh port
* def_cs_db - default connect string for the target database instance
* def_cs_asm - default connect string for the target ASM instance

* ora_src_usr - source database username
* ora_src_pwd - source database password
* ora_src_cs - source database connect string
* ora_backup_mode - whether to use Oracle backup mode - overriden by command line option

* tgt_host - target host to start cloned database on
* tgt_db - target database name
* tgt_user_grid  - target account username that owns ASM/Grid Infrastructure
* tgt_pass_grid - target account password that owns ASM/Grid Infrastructure
* tgt_sid - target SID to mount the clone

* local_listener - the listener the target database is to register with
* db_unique_name - the db_unique_name setting of the cloned database 
    
# Notes:

Unlike fa_pg_ora_snap.py, this code can execute on a remote scripting host.\
This code required password-less sudo privileges to execute the rescan_afd.sh or rescan_udev.sh script.\
If replication is NOT specified, both the source and target protection groups are assumed to be on the source Flash Array, and the target Flash Array is ignored.\
A JSON file must be specified to provide the authentication details to the source and target servers.

# Tagging the database snapshot

The python code adds numerous tags to the database snapshot.  This allows the DBA to recover the database from the snapshot at a later time when, perhaps, the source database is no longer available to inspect.\
The tags include the database time the snapshot was made, which allows the use of the "recover database snapshot time" syntax.\
Tags also include the database ID, database name, if the database was in backup mode or not, and the location of the database controlfiles.

# A Worked Example

In the example below, the database SWINGDB is running on Linux server rdmudev01.  It has its ASM diskgroups in a Pure Flash Array protection group called gct-oradb-rdmudev01-pg\
The code will place the source database into backup mode, snapshot that protection group, and then overwrite correspodning volumes on Linux server rdmudev02, where Oracle is also installed.  The code will then mount the cloned ASM diskgroups on rdmudev02, mount the cloned database and open it read-write.\
All of this is exeuted remotely from a scripting host.\


```
$ python fa_pg_ora_snap_remote.py -f rdmudev01_2_rdmudev02_remote.json -n dec161217 -x -b -o open
============
fa_pg_ora_snap_remote.py 1.9.0 started at 2025-12-16 12:17:50.416204
============
connecting to Flash Array:sn1-x90r2-f06-27.puretec.purestorage.com
connected
============
determining if snapshot dec161217 exists for protection group:gct-oradb-rdmudev01-pg
source protection group:gct-oradb-rdmudev01-pg
target protection group:gct-oradb-rdmudev02-pg
============
connecting to source database:gct-oradb-rdmudev01:1521/swingdb
use backup mode:True
============
reading source database settings
asm diskgroups: SWINGDATA
database name: SWINGDB
database id: 4017528888
database time: 2025/12/16 12:17:50
database open mode: READ WRITE
database role: PRIMARY
encrypted tablespaces: 0
archivelog mode: ARCHIVELOG
flashback mode: NO
platform name: Linux x86 64-bit
version: Oracle Database 19c Enterprise Edition Release 19.0.0.0.0 - Production,Version 19.22.0.0.0
control_files: +SWINGDATA/SWINGDB/CONTROLFILE/current.266.1201708985, +SWINGDATA/SWINGDB/CONTROLFILE/current.265.1201708985
db_recovery_file_dest: /nfsmnt/oradb/recovery/gct-oradb-rdmudev01/swingprd
db_recovery_file_dest_size: 107374182400
enable_pluggable_database: FALSE
============
source db begin backup mode
============
creating snapshot for gct-oradb-rdmudev01-pg
============
source db end backup mode
============
querying the volumes for protection group:gct-oradb-rdmudev01-pg
gct-oradb-rdmudev01-00
gct-oradb-rdmudev01-01
============
tagging the snapshot: key:db_name val:SWINGDB
tagging the snapshot: key:db_id val:4017528888
tagging the snapshot: key:db_time val:2025/12/16 12:17:50
tagging the snapshot: key:db_unique_name val:SWINGDB
tagging the snapshot: key:db_role val:PRIMARY
tagging the snapshot: key:db_open_mode val:READ WRITE
tagging the snapshot: key:archivelog_mode val:ARCHIVELOG
tagging the snapshot: key:flashback_mode val:NO
tagging the snapshot: key:platform_name val:Linux x86 64-bit
tagging the snapshot: key:encrypted_tablespaces val:0
tagging the snapshot: key:version val:Oracle Database 19c Enterprise Edition Release 19.0.0.0.0 - Production,Version 19.22.0.0.0
tagging the snapshot: key:backup_mode val:Yes
tagging the snapshot: key:control_files val:+SWINGDATA/SWINGDB/CONTROLFILE/current.266.1201708985, +SWINGDATA/SWINGDB/CONTROLFILE/current.265.1201708985
tagging the snapshot: key:db_recovery_file_dest val:/nfsmnt/oradb/recovery/gct-oradb-rdmudev01/swingprd
tagging the snapshot: key:db_recovery_file_dest_size val:107374182400
tagging the snapshot: key:enable_pluggable_database val:FALSE
tagging the snapshot: key:asm_disk_groups val:SWINGDATA
tagging the snapshot: key:open_pdbs val:Not Defined
============
excluded volumes
============
listing the volumes for snapshot:dec161217
name:gct-oradb-rdmudev01-pg.dec161217.gct-oradb-rdmudev01-00 size:74.0 GB
name:gct-oradb-rdmudev01-pg.dec161217.gct-oradb-rdmudev01-01 size:74.0 GB
============
checking target instance swingdev on host gct-oradb-rdmudev02 is down
============
checking target ASM diskgroups are unmounted: SWINGDATA
============
querying the volumes for protection group:gct-oradb-rdmudev02-pg
gct-oradb-rdmudev02-00
gct-oradb-rdmudev02-01
============
querying target volume details
name:gct-oradb-rdmudev02-00 id:9cbf36fe-55c3-acde-33be-bf54ac681b57 size:74.0
   is a target for gct-oradb-rdmudev01-pg.dec161217.gct-oradb-rdmudev01-00 size:74.0 GB
name:gct-oradb-rdmudev02-01 id:0cbbb69f-f846-c0e9-81eb-b39ad669e0d3 size:74.0
   is a target for gct-oradb-rdmudev01-pg.dec161217.gct-oradb-rdmudev01-01 size:74.0 GB
============
determining volume mapping
nm:gct-oradb-rdmudev01-pg.dec161217.gct-oradb-rdmudev01-00 src id:f6e6c606-c82a-947f-69b4-9f92775a8d51 map:0 sz:74.0
  checking for tag matched volume
    volume gct-oradb-rdmudev01-pg.dec161217.gct-oradb-rdmudev01-00 will be synced to gct-oradb-rdmudev02-00
nm:gct-oradb-rdmudev01-pg.dec161217.gct-oradb-rdmudev01-01 src id:5dc6f5c3-9f65-d5ad-18b3-17c63d7459e4 map:0 sz:74.0
  checking for tag matched volume
    volume gct-oradb-rdmudev01-pg.dec161217.gct-oradb-rdmudev01-01 will be synced to gct-oradb-rdmudev02-01
============
mapping the volumes
gct-oradb-rdmudev01-pg.dec161217.gct-oradb-rdmudev01-00 will be syncd to gct-oradb-rdmudev02-00
gct-oradb-rdmudev01-pg.dec161217.gct-oradb-rdmudev01-01 will be syncd to gct-oradb-rdmudev02-01
============
rescaning the SCSI bus on target gct-oradb-rdmudev02
============
mounting ASM diskgroups on target gct-oradb-rdmudev02
============
checking target ASM diskgroups are mounted: SWINGDATA
ASM diskgroup SWINGDATA mounted on target
============
requested state of swingdev is:OPEN
resetting the target SPFILE
alter system set db_name='SWINGDB' sid='*' scope=spfile;
alter system set control_files='+SWINGDATA/SWINGDB/CONTROLFILE/current.266.1201708985','+SWINGDATA/SWINGDB/CONTROLFILE/current.265.1201708985' sid='*' scope=spfile;
alter system set db_recovery_file_dest='/nfsmnt/oradb/recovery/gct-oradb-rdmudev01/swingprd' sid='*' scope=spfile;
alter system set db_recovery_file_dest_size=107374182400 sid='*' scope=spfile;
alter system set enable_pluggable_database=FALSE sid='*' scope=spfile;
restarting instance
actual state of swingdev on host gct-oradb-rdmudev02 is:OPEN
============
complete

```
