# Python scripts for snapshot and cloning an Oracle database on an Everpure Flash Array on remote servers

The script fa_pg_ora_snap.rac.py provides for taking a snapshot clone of an Oracle database using ASM, with volumes in a protection group on an Everpure Flash Array.\
This script can be executed from a remote Linux scripting host.  The source database is accessed with python-oracledb, and the target hosts are accessed over SSH.  It can clone both single instance and RAC clustered databases.\
The code can also clone the source database to a target database server or RAC cluster.  The code will check whether the target database and ASM diskgroups are offline before execution.  If they are still online, the code will refuse to execute.\
It will also optionally copy that snapshot to a target protection group.  In this case the target protection group must have an equal or greater number of volumes of equal or larger size than the source.\
The script can also copy an existing snapshot of a source protection group to a target protection group.  In this case the database settings are read back from the tags on the snapshot.\
If replication is set up for the source protection group, the snapshot can be replicated to a second Flash Array.

# Requirements:

- Python 3.8 or later
- py-pure-client (`python -m pip install py-pure-client`)
- python-oracledb (`python -m pip install oracledb`)
- paramiko and cryptography (`python -m pip install paramiko cryptography`)
- `python -m pip install 'setuptools<72.0.0'`
- SSH access to the target hosts as the grid and oracle users, by password or key (RSA, Ed25519, ECDSA and DSA key files are supported)
- `oraenv`, `srvctl`, `asmcmd` and SQL*Plus available on the target hosts
- This Python code imports the [fa_pg_snap.py](../fa_pg_snap/) code.
- This Python code imports the [fa_pg_ora_snap.py](../fa_pg_ora_snap/) code.

# Arguments:

-s source protection group (required unless `source_protection_group` or `src_protection_group` is set in the JSON config file)\
-t target protection group (optional - may also be set with `target_protection_group` or `tgt_protection_group` in the JSON config file)\
-n the snapshot name.  If this does not exist - it will create it.  If it already exists, it will use the existing snapshot to sync to the target, reading the database settings from the snapshot tags. (required)\
-f JSON file with FQDN and API token to connect to the Flash Arrays, plus the database and target host settings (required)\
-r replicate the snapshot to the targets specified in the source protection group (optional)\
-o startup mode of the target database (OPEN, MOUNT, NOMOUNT or DOWN - case insensitive, defaults to DOWN)\
-b use oracle backup mode (optional - defaults to no)\
-i ignore tag (override established source/target volume pairing for cloning - see fa_pg_ora_snap.py for more details)\
-d debug level 0-4 (optional - defaults to 0)\
-x execute lock - if this is NOT set, no destructive actions will be taken.  Instead, the script will simply tell you what it would do.  This may prove useful to make sure you have all the settings right before you overwrite a target protection group.\
Note - many database parameters must be specified in the JSON file - see below:

# JSON file settings:

* src_flash_array_host - FQDN of the source Everpure Flash Array (required).
* src_flash_array_api_token - API token to authenticate against the source Everpure Flash Array (required).
* flash_array_api_version - API version to use to connect to Purity (optional - auto-negotiated when omitted).
* tgt_flash_array_host - FQDN of the target Everpure Flash Array (optional - if replicating).
* tgt_flash_array_api_token - API token to authenticate against the target Everpure Flash Array (optional - if replicating).
* source_protection_group (or src_protection_group) - Everpure Flash Array protection group that includes all ASM disks in the source database (required).
* target_protection_group (or tgt_protection_group) - Everpure Flash Array protection group that includes all ASM disks in the target database (optional - if cloning database).
* replicate - "True" to replicate the snapshot (the -r flag also enables this)
* excluded_volumes - list of source volume IDs to exclude from the sync (optional)
* rescan_scsi_bus - how to scan for new ASM disks (two examples are included in the repository)
* oracle_target_mode - requested state of cloned database (OPEN, MOUNT, NOMOUNT or DOWN) - overridden by the -o command line option

* def_user_oracle - default oracle username if no other is provided (defaults to oracle)
* def_pass_oracle - default oracle password if no other is provided
* def_user_grid - default grid username if no other is provided (defaults to the oracle username)
* def_pass_grid - default grid password if no other is provided (defaults to the oracle password)
* def_port - default ssh port (defaults to 22)
* def_cs_db - default connect string for the target database instance (defaults to "connect / as sysdba")

* ora_src_usr - source database username
* ora_src_pwd - source database password
* ora_src_cs - source database connect string
* ora_backup_mode - "True" to use Oracle backup mode (the -b flag also enables this)

* tgt_hosts - a list of the target hosts to mount the cloned database on (use one entry for single instance).  Each entry is an object with a tgt_host key, for example: `[ {"tgt_host": "node1.example.com"}, {"tgt_host": "node2.example.com"} ]`
* tgt_port - ssh port for the target hosts (optional - falls back to def_port)
* tgt_db - target database name as registered with Grid Infrastructure (required when tgt_hosts is set)
* tgt_cs_db - connect string for the target database instance (optional - falls back to def_cs_db)
* tgt_user_grid - target account username that owns ASM/Grid Infrastructure (if not set, uses the oracle username instead)
* tgt_pass_grid - target account password that owns ASM/Grid Infrastructure (ignored if tgt_key_grid used)
* tgt_key_grid - ssh keyfile to use to provide password-less access to the remote host as the grid account (optional - if the grid and oracle usernames match, tgt_key_oracle is used automatically)
* tgt_user_oracle - target account username that owns Oracle
* tgt_pass_oracle - target account password that owns Oracle (ignored if tgt_key_oracle used)
* tgt_key_oracle - ssh keyfile to use to provide password-less access to the remote host as the oracle account (optional)

* local_listener - the listener the cloned pluggable databases are to register with (optional)
* db_unique_name - the db_unique_name setting of the cloned database (optional)

# Notes:

Unlike fa_pg_ora_snap.py, this code can execute on a remote scripting host.\
The ASM instance on each target host is discovered automatically over SSH - it does not need to be configured.\
This code requires password-less sudo privileges to execute the rescan_asmlib.sh, rescan_afd.sh or rescan_udev.sh script.\
If replication is NOT specified, both the source and target protection groups are assumed to be on the source Flash Array, and the target Flash Array is ignored.\
If the JSON file does not specify Flash Array authentication credentials, the code will try the OS variables FA_HOST/API_TOKEN (source) and FA_HOST_TGT/API_TOKEN_TGT (target).\
A JSON file must be specified to provide the authentication details to the source database and target server(s).

# Tagging the database snapshot

The python code adds numerous tags to the database snapshot.  This allows the DBA to recover the database from the snapshot at a later time when, perhaps, the source database is no longer available to inspect.\
The tags include the database time the snapshot was made, which allows the use of the "recover database snapshot time" syntax.\
Tags also include the database ID, database name, if the database was in backup mode or not, the location of the database controlfiles, the ASM diskgroups in use, and any open pluggable databases.\
A replicate tag records whether the snapshot was created with replication; if -r is used against an existing snapshot, this tag is checked and the script stops if the snapshot was not replicated when it was created (a warning is printed if the snapshot carries no replicate tag).\
When an existing snapshot is used, these tags are read back and used to reset the SPFILE of the cloned database.

# A Worked Example

In the example below, the database PRDCDB is running on a pair of Linux servers.  It has its ASM diskgroups in an Everpure Flash Array protection group called gct-oradb-rac-prd-data-pg\
The code will place the source database into backup mode, snapshot that protection group, and then overwrite corresponding volumes on Linux RAC cluster gct-oradb-tst-rac01 and gct-oradb-tst-rac02.  The code will then mount the cloned ASM diskgroups on the target RAC cluster, mount the cloned database and open it read-write.\
All of this is executed remotely from a scripting host.\


```
[oracle@gct-oradb-demo-tst01 py]$ python fa_pg_ora_snap.rac.py -f json/prdrac_2_tstrac.json -n jun121246 -r -x -b -o open
============
fa_pg_ora_snap.rac.py 1.9.0 started at 2026-06-12 12:52:42.908169
============
connecting to Flash Array:sn1-x90r2-f06-27.puretec.purestorage.com API Version:2.44
connected
============
connecting to Flash Array:sn1-x90r2-f05-33.puretec.purestorage.com API Version:2.44
connected
============
determining if snapshot jun121246 exists for protection group:gct-oradb-rac-prd-data-pg
snapshot jun121246 exists
source protection group:gct-oradb-rac-prd-data-pg
target protection group:gct-oradb-rac-tst-data-pg
============
reading tags from snapshot
tags for gct-oradb-rac-prd-data-pg.jun121246:
db_name PRDCDB
db_id 3749697885
db_time 2026/06/12 14:48:32
db_unique_name prdcdb
db_role PRIMARY
db_threads 2
db_open_mode READ WRITE
archivelog_mode ARCHIVELOG
flashback_mode NO
platform_name Linux x86 64-bit
encrypted_tablespaces 0
version Oracle Database 19c Enterprise Edition Release 19.0.0.0.0 - Production,Version 19.22.0.0.0
backup_mode Yes
control_files +DATA/PRDCDB/CONTROLFILE/current.308.1233917149, +DATA/PRDCDB/CONTROLFILE/current.307.1233917149
db_recovery_file_dest +DATA
db_recovery_file_dest_size 13979615232
enable_pluggable_database TRUE
asm_disk_groups DATA
open_pdbs PRDPDB
replicate True
============
querying the volumes for protection group:gct-oradb-rac-prd-data-pg on array sn1-x90r2-f06-27
gct-oradb-rac-prd-data00
gct-oradb-rac-prd-data01
gct-oradb-rac-prd-data02
============
excluded volumes
============
listing the volumes for snapshot:jun121246
name:sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun121246.gct-oradb-rac-prd-data00 sz:100.0 GB
name:sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun121246.gct-oradb-rac-prd-data01 sz:100.0 GB
name:sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun121246.gct-oradb-rac-prd-data02 sz:100.0 GB
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
nm:gct-oradb-rac-tst-data00
  id:c16f124e-ac41-74da-77e7-932cc21092b9
  is a target for sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun121246.gct-oradb-rac-prd-data00
  sz:100.0 GB
nm:gct-oradb-rac-tst-data01
  id:ed666ee9-fb96-4ff9-7696-2ecde5492187
  is a target for sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun121246.gct-oradb-rac-prd-data01
  sz:100.0 GB
nm:gct-oradb-rac-tst-data02
  id:3e490b40-7d8b-e9c7-0c27-7a0dad0c8bcd
  is a target for sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun121246.gct-oradb-rac-prd-data02
  sz:100.0 GB
============
determining volume mapping
nm:sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun121246.gct-oradb-rac-prd-data00
  src id:c3b11b19-a44f-aaf1-9a5b-dc6f91fe356f map:0
  sz:100.0 GB
  checking for tag matched volume
  will be synced to gct-oradb-rac-tst-data00
nm:sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun121246.gct-oradb-rac-prd-data01
  src id:227a2b95-ef7b-2bf2-f4f3-a98bea8281b8 map:0
  sz:100.0 GB
  checking for tag matched volume
  will be synced to gct-oradb-rac-tst-data01
nm:sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun121246.gct-oradb-rac-prd-data02
  src id:e80706ce-7473-8eae-9b90-7666d6d97da7 map:0
  sz:100.0 GB
  checking for tag matched volume
  will be synced to gct-oradb-rac-tst-data02
============
mapping the volumes
sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun121246.gct-oradb-rac-prd-data00
  src key:c3b11b19-a44f-aaf1-9a5b-dc6f91fe356f
  map:c16f124e-ac41-74da-77e7-932cc21092b9
  will be syncd to gct-oradb-rac-tst-data00
sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun121246.gct-oradb-rac-prd-data01
  src key:227a2b95-ef7b-2bf2-f4f3-a98bea8281b8
  map:ed666ee9-fb96-4ff9-7696-2ecde5492187
  will be syncd to gct-oradb-rac-tst-data01
sn1-x90r2-f06-27:gct-oradb-rac-prd-data-pg.jun121246.gct-oradb-rac-prd-data02
  src key:e80706ce-7473-8eae-9b90-7666d6d97da7
  map:3e490b40-7d8b-e9c7-0c27-7a0dad0c8bcd
  will be syncd to gct-oradb-rac-tst-data02
============
rescaning the SCSI bus on target gct-oradb-tst-rac01.localdomain
rescaning the SCSI bus on target gct-oradb-tst-rac02.localdomain
============
mounting ASM diskgroups on host gct-oradb-tst-rac01.localdomain using ASM instance +ASM1
mounting ASM diskgroups on host gct-oradb-tst-rac02.localdomain using ASM instance +ASM2
============
checking target ASM diskgroups are mounted DATA on host gct-oradb-tst-rac01.localdomain
target ASM diskgroup DATA is mounted on node 2
target ASM diskgroup DATA is mounted on node 1
============
checking target ASM diskgroups are mounted DATA on host gct-oradb-tst-rac02.localdomain
target ASM diskgroup DATA is mounted on node 2
target ASM diskgroup DATA is mounted on node 1
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
opening PRDPDB
actual state of cdbtst1 on host gct-oradb-tst-rac01.localdomain is:OPEN
============
complete


```
