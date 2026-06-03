# Python scripts for snapshot and cloning an Oracle database on Pure Flash Array on remote servers

The script fa_pg_ora_snap.rac.py provides for taking a snapshot clone of an Oracle database using ASM, with volumes in a protection group on a Pure Flash Array.\
This script can be executed from a remote Linux server.  It requires a SQL client to be installed to access to the source database.  It can clone both single instance and RAC clustered databases.\
The code can also clone the source database to a target database server.  The code will check to determine of the target database and ASM diskgroups are offline before execution.  If they are still online, the code will refuse to execute.\
It will also optionally copy that snapshot to a target protection group.  In this case the target protection group must have an equal or greater number of volumes of equal or larger size than the source.\
The script can also copy an existing snapshot of a source protection group to a target protection group.\
If replication is set up for the source protection group, the snapshot can be replicated to a second Flash Array.

# Requirements:

This Python code imports the [fa_pg_snap.py](../fa_pg_snap/) code.\
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
* flash_array_api_version - API version to use to connect to Purity.
* tgt_flash_array_host - FQDN of the target Pure Flash Array (optional - if replicating).
* tgt_flash_array_api_token - API token to authenticate against the target Pure Flash Array (optional - if replicating).
* src_protection_group - Pure Flash Array protection group that includes all ASM disks in the source database (required).
* tgt_protection_group - Pure Flash Array protection group that includes all ASM disks in the target database (optional - if cloning database).
* replicate - replicate the snapshot (True or False)
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

* tgt_hosts - a list of the target hosts to mount the cloned database on (use one for single instance)
* tgt_db - target database name
* tgt_user_grid  - target account username that owns ASM/Grid Infrastructure (if not set, uses oracle instead)
* tgt_pass_grid - target account password that owns ASM/Grid Infrastructure (ignored if tgt_key_grid used)
* tgt_key_grid - ssh keyfile to use to provide password-less access to the remote host as the grid account (optional)
* tgt_user_oracle  - target account username that owns Oracle
* tgt_pass_oracle - target account password that owns Oracle (ignored if tgt_key_oracle used)
* tgt_key_oracle - ssh keyfile to use to provide password-less access to the remote host as the oracle account (optional)

* db_unique_name - the db_unique_name setting of the cloned database 
    
# Notes:

Unlike fa_pg_ora_snap.py, this code can execute on a remote scripting host.\
This code requires password-less sudo privileges to execute the rescan_asmlib.sh, rescan_afd.sh or rescan_udev.sh script.\
If replication is NOT specified, both the source and target protection groups are assumed to be on the source Flash Array, and the target Flash Array is ignored.\
A JSON file must be specified to provide the authentication details to the source database and target server(s).

# Tagging the database snapshot

The python code adds numerous tags to the database snapshot.  This allows the DBA to recover the database from the snapshot at a later time when, perhaps, the source database is no longer available to inspect.\
The tags include the database time the snapshot was made, which allows the use of the "recover database snapshot time" syntax.\
Tags also include the database ID, database name, if the database was in backup mode or not, and the location of the database controlfiles.

# A Worked Example

In the example below, the database PRDCDB is running on a pair of Linux servers.  It has its ASM diskgroups in a Pure Flash Array protection group called gct-oradb-rac-prd-data-pg\
The code will place the source database into backup mode, snapshot that protection group, and then overwrite corresponding volumes on Linux RAC cluster gct-oradb-tst-rac01 and gct-oradb-tst-rac02.  The code will then mount the cloned ASM diskgroups on the target RAC cluster, mount the cloned database and open it read-write.\
All of this is exeuted remotely from a scripting host.\


```
$[oracle@gct-oradb-demo-tst01 py]$ python fa_pg_ora_snap.rac.py -f json/clone_rac_database.json -n jun021703 -r -x -b -o open
============
fa_pg_ora_snap.rac.py 1.9.0 started at 2026-06-02 17:03:40.073971
============
connecting to Flash Array:sn1-x90r2-f06-27.puretec.purestorage.com API Version:2.27
connected
============
connecting to Flash Array:sn1-x90r2-f05-33.puretec.purestorage.com API Version:2.27
connected
============
determining if snapshot jun021703 exists for protection group:gct-oradb-rac-prd-data-pg
source protection group:gct-oradb-rac-prd-data-pg
target protection group:gct-oradb-rac-tst-data-pg
============
connecting to source database:gct-oradb-prd-rac02.localdomain:1521/prdcdb
use backup mode:True
============
reading source database settings
asm diskgroups: DATA
database name: PRDCDB
database id: 3749697885
database time: 2026/06/02 19:03:40
database open mode: READ WRITE
database role: PRIMARY
database threads: 2
encrypted tablespaces: 0
archivelog mode: ARCHIVELOG
flashback mode: NO
platform name: Linux x86 64-bit
version: Oracle Database 19c Enterprise Edition Release 19.0.0.0.0 - Production,Version 19.22.0.0.0
control_files: +DATA/PRDCDB/CONTROLFILE/current.308.1233917149, +DATA/PRDCDB/CONTROLFILE/current.307.1233917149
db_recovery_file_dest: +DATA
db_recovery_file_dest_size: 13979615232
enable_pluggable_database: TRUE
identifying the open pluggable databases
no open pluggable databases found
============
source db begin backup mode
============
creating snapshot for gct-oradb-rac-prd-data-pg
============
source db end backup mode
============
querying the volumes for protection group:gct-oradb-rac-prd-data-pg on array sn1-x90r2-f06-27
gct-oradb-rac-prd-data00
gct-oradb-rac-prd-data01
gct-oradb-rac-prd-data02
============
tagging the snapshot: key:db_name val:PRDCDB
tagging the snapshot: key:db_id val:3749697885
tagging the snapshot: key:db_time val:2026/06/02 19:03:40
tagging the snapshot: key:db_unique_name val:prdcdb
tagging the snapshot: key:db_role val:PRIMARY
tagging the snapshot: key:db_threads val:2
tagging the snapshot: key:db_open_mode val:READ WRITE
tagging the snapshot: key:archivelog_mode val:ARCHIVELOG
tagging the snapshot: key:flashback_mode val:NO
tagging the snapshot: key:platform_name val:Linux x86 64-bit
tagging the snapshot: key:encrypted_tablespaces val:0
tagging the snapshot: key:version val:Oracle Database 19c Enterprise Edition Release 19.0.0.0.0 - Production,Version 19.22.0.0.0
tagging the snapshot: key:backup_mode val:Yes
tagging the snapshot: key:control_files val:+DATA/PRDCDB/CONTROLFILE/current.308.1233917149, +DATA/PRDCDB/CONTROLFILE/current.307.1233917149
tagging the snapshot: key:db_recovery_file_dest val:+DATA
tagging the snapshot: key:db_recovery_file_dest_size val:13979615232
tagging the snapshot: key:enable_pluggable_database val:TRUE
tagging the snapshot: key:asm_disk_groups val:DATA
tagging the snapshot: key:open_pdbs val:Not Defined
============
excluded volumes
============
listing the volumes for snapshot:jun021703
name:sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun021703.gct-oradb-rac-prd-data00 size:100.0 GB
name:sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun021703.gct-oradb-rac-prd-data01 size:100.0 GB
name:sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun021703.gct-oradb-rac-prd-data02 size:100.0 GB
============
will use ssh key to connect as grid
will use ssh key to connect as oracle
============
determining ASM instance on host gct-oradb-tst-rac01.localdomain
ASM instance on this host is +ASM1
checking if target database cdbtst is configured on host gct-oradb-tst-rac01.localdomain
checking if target database cdbtst is running on any host
============
checking target ASM diskgroups are unmounted DATA on host gct-oradb-tst-rac01.localdomain
============
determining ASM instance on host gct-oradb-tst-rac02.localdomain
ASM instance on this host is +ASM2
checking if target database cdbtst is configured on host gct-oradb-tst-rac02.localdomain
checking if target database cdbtst is running on any host
============
checking target ASM diskgroups are unmounted DATA on host gct-oradb-tst-rac02.localdomain
============
querying the volumes for protection group:gct-oradb-rac-tst-data-pg on array sn1-x90r2-f05-33
gct-oradb-rac-tst-data00
gct-oradb-rac-tst-data01
gct-oradb-rac-tst-data02
============
querying target volume details
name:gct-oradb-rac-tst-data00 id:c16f124e-ac41-74da-77e7-932cc21092b9 size:100.0
   is a target for sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun021703.gct-oradb-rac-prd-data00 size:100.0 GB
name:gct-oradb-rac-tst-data01 id:ed666ee9-fb96-4ff9-7696-2ecde5492187 size:100.0
   is a target for sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun021703.gct-oradb-rac-prd-data01 size:100.0 GB
name:gct-oradb-rac-tst-data02 id:3e490b40-7d8b-e9c7-0c27-7a0dad0c8bcd size:100.0
   is a target for sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun021703.gct-oradb-rac-prd-data02 size:100.0 GB
============
determining volume mapping
nm:sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun021703.gct-oradb-rac-prd-data00 src id:7ca9b19a-a260-23b0-032f-590897297e0e map:0 sz:100.0
  checking for tag matched volume
    volume sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun021703.gct-oradb-rac-prd-data00 will be synced to gct-oradb-rac-tst-data00
nm:sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun021703.gct-oradb-rac-prd-data01 src id:a6293a28-a82f-60ec-df1c-d7f6000d858d map:0 sz:100.0
  checking for tag matched volume
    volume sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun021703.gct-oradb-rac-prd-data01 will be synced to gct-oradb-rac-tst-data01
nm:sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun021703.gct-oradb-rac-prd-data02 src id:17dfedda-e53f-cdcb-0754-23956596aec2 map:0 sz:100.0
  checking for tag matched volume
    volume sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun021703.gct-oradb-rac-prd-data02 will be synced to gct-oradb-rac-tst-data02
============
waiting on snapshot replication
============
tagging the snapshot: key:db_name val:PRDCDB
tagging the snapshot: key:db_id val:3749697885
tagging the snapshot: key:db_time val:2026/06/02 19:03:40
tagging the snapshot: key:db_unique_name val:prdcdb
tagging the snapshot: key:db_role val:PRIMARY
tagging the snapshot: key:db_threads val:2
tagging the snapshot: key:db_open_mode val:READ WRITE
tagging the snapshot: key:archivelog_mode val:ARCHIVELOG
tagging the snapshot: key:flashback_mode val:NO
tagging the snapshot: key:platform_name val:Linux x86 64-bit
tagging the snapshot: key:encrypted_tablespaces val:0
tagging the snapshot: key:version val:Oracle Database 19c Enterprise Edition Release 19.0.0.0.0 - Production,Version 19.22.0.0.0
tagging the snapshot: key:backup_mode val:Yes
tagging the snapshot: key:control_files val:+DATA/PRDCDB/CONTROLFILE/current.308.1233917149, +DATA/PRDCDB/CONTROLFILE/current.307.1233917149
tagging the snapshot: key:db_recovery_file_dest val:+DATA
tagging the snapshot: key:db_recovery_file_dest_size val:13979615232
tagging the snapshot: key:enable_pluggable_database val:TRUE
tagging the snapshot: key:asm_disk_groups val:DATA
tagging the snapshot: key:open_pdbs val:Not Defined
============
mapping the volumes
sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun021703.gct-oradb-rac-prd-data00 will be syncd to gct-oradb-rac-tst-data00
sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun021703.gct-oradb-rac-prd-data01 will be syncd to gct-oradb-rac-tst-data01
sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun021703.gct-oradb-rac-prd-data02 will be syncd to gct-oradb-rac-tst-data02
============
rescaning the SCSI bus on target gct-oradb-tst-rac01.localdomain
rescaning the SCSI bus on target gct-oradb-tst-rac02.localdomain
============
mounting ASM diskgroups on host gct-oradb-tst-rac01.localdomain using ASM instance +ASM1
mounting ASM diskgroups on host gct-oradb-tst-rac02.localdomain using ASM instance +ASM2
============
checking target ASM diskgroups are mounted DATA on host gct-oradb-tst-rac01.localdomain
target ASM diskgroup DATA is mounted on node gct-oradb-tst-rac01.localdomain
============
checking target ASM diskgroups are mounted DATA on host gct-oradb-tst-rac02.localdomain
target ASM diskgroup DATA is mounted on node gct-oradb-tst-rac02.localdomain
============
requested state of cdbtst is:OPEN
starting database cdbtst to a NOMOUNT state using host gct-oradb-tst-rac01.localdomain and database instance cdbtst1
============
resetting the target SPFILE on host gct-oradb-tst-rac01.localdomain using instance cdbtst1
alter system set db_name='PRDCDB' sid='*' scope=spfile;
alter system set control_files='+DATA/PRDCDB/CONTROLFILE/current.308.1233917149','+DATA/PRDCDB/CONTROLFILE/current.307.1233917149' sid='*' scope=spfile;
alter system set db_recovery_file_dest='+DATA' sid='*' scope=spfile;
alter system set db_recovery_file_dest_size=13979615232 sid='*' scope=spfile;
alter system set enable_pluggable_database=TRUE sid='*' scope=spfile;
shutting down database cdbtst using host gct-oradb-tst-rac01.localdomain and database instance cdbtst1
============
restarting target database
starting database cdbtst to a OPEN state using host gct-oradb-tst-rac01.localdomain and database instance cdbtst1
taking target database out of backup mode using instance cdbtst1
restarting target database with backup mode disabled
re-opening pluggable databases
no pluggable databases to re-open
actual state of cdbtst1 on host gct-oradb-tst-rac01.localdomain is:OPEN
============
complete

```
