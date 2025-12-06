# Python scripts for snapshot and cloning a protection group on a Pure Flash Array

The script fa_pg_snap.py provides for taking a snapshot of a protection group on a Pure Flash Array.\
It will also optionally copy that snapshot to a target protection group.  In this case the target protection group must have an equal or greater number of volumes of equal or larger size than the source.\
The script can also copy an existing snapshot of a source protection group to a target protection group.\
If replication is set up for the source protection group, the snapshot can be replicated to a second Flash Array.

# Arguments:

-s source protection group (required)\
-t target protection group (optional)\
-n the snapshot name.  If this does not exist - it will create it.  If it already exists, it will use the existing snapshot to sync to the target. (required)\
-f JSON file with FQDN and API token to connect to the Flash Arrays (required)\
-r replicate the snapshot to the targets specified in the source protection group (optional)\
-o output file with the names of the snapshot volumes (optional)\
-i ignore tag (optional - see below)\
-x execute lock - if this is NOT set, no destructive actions will be taken.  Instead, the script will simply tell you would it would do.  This may prove useful to make sure you have all the settings right before you  overwrite a target protection group.

# Notes:

If replication is not specified, both the source and target protection groups are assumed to be on the source Flash Array, and the target Flash Array is ignored.\
If the JSON file does not specify authentication credentials, the code will try to read the OS variables FA_HOST and API_TOKEN for authentication to the source Flash Array.\
If the JSON file does not specify authentication credentials, the code will try to read the OS variables FA_HOST_TGT and API_TOKEN_TGT for authentication to the target Flash Array.

# Excluding Volumes in the Protection Group

In some scenarios you may with to exclude volumes from the snapshot-copy.  For example, VVOLs include a config VVOL that must NOT be overwritten.\
In this example, the JSON file allows the user to specify source volumes in the protection group that will NOT be sync'd to target volumes in the target protection group.

# Source snapshot/target volume pairing

If a target protection group is specified, the code will overwrite the volumes of the target protection group with the contents of the source snapshot.\
To achieve this, the code will look for matching volumes of the same size.  If none can be found, then the code will consider volumes of larger size.  Volumes are considered in alphabetical order, so if the same naming convention is used for both source and target, the volumes will be considered in order.  Once a suitable target has been identified, the code tags the volume of the target protection group with the volume id of the source volume.  This means that every subsequent execution of the code wil see the same target volume ovewritten from the same source snapshot volume.
The -i flag may be used to ignore these tags and re-establish a new source-snapshot/target volume pairing, such as the user decides to snapshot from a different source protection group.

# A Worked Example

In the example below, the source protection group gct-oradb-demo-prd01-pg is snapshot and then sync'd to the target protection group gct-oradb-demo-dev01-pg.\
The JSON file excludes two volumes from the snapshot/sync process.

<code>
[oracle@gct-oradb-demo-dev01 py]$  python fa_pg_snap.py -f fa27b.json -n dec051707 -s gct-oradb-demo-prd01-pg -t gct-oradb-demo-dev01-pg -x
============
fa_pg_snap.py 1.0.0 started at 2025-12-05 17:07:36.791237
============
connecting to Flash Array:sn1-x90r2-f06-27.puretec.purestorage.com
connected
============
determining if snapshot dec051707 exists for source pg:gct-oradb-demo-prd01-pg
source protection group:gct-oradb-demo-prd01-pg
target protection group:gct-oradb-demo-dev01-pg
============
querying the volumes for protection group:gct-oradb-demo-prd01-pg
gct-oradb-demo-prd01-data-00
gct-oradb-demo-prd01-data-01
gct-oradb-demo-prd01-fra-00
gct-oradb-demo-prd01-fra-01
============
querying the volumes for protection group:gct-oradb-demo-dev01-pg
gct-oradb-demo-dev01-data-00
gct-oradb-demo-dev01-data-01
gct-oradb-demo-dev01-fra-00
gct-oradb-demo-dev01-fra-01
============
creating snapshot for gct-oradb-demo-prd01-pg
============
excluding:{'volume_id': 'dd246ff7-9104-71cd-0320-8915f47aa77e'}
excluding:{'volume_id': 'dd246ff7-9104-71cd-0320-8915f47aa77f'}
============
listing the volumes for snapshot:dec051707
name:gct-oradb-demo-prd01-pg.dec051707.gct-oradb-demo-prd01-data-00 size:120.0 GB
name:gct-oradb-demo-prd01-pg.dec051707.gct-oradb-demo-prd01-data-01 size:120.0 GB
name:gct-oradb-demo-prd01-pg.dec051707.gct-oradb-demo-prd01-fra-00 size:40.0 GB
name:gct-oradb-demo-prd01-pg.dec051707.gct-oradb-demo-prd01-fra-01 size:40.0 GB
============
querying the volumes for protection group:gct-oradb-demo-dev01-pg
gct-oradb-demo-dev01-data-00
gct-oradb-demo-dev01-data-01
gct-oradb-demo-dev01-fra-00
gct-oradb-demo-dev01-fra-01
============
querying target volume details
name:gct-oradb-demo-dev01-data-00 id:a67641ac-9a36-c375-baf1-298c8a98ffe5 size:120.0
   is a target for gct-oradb-demo-prd01-pg.dec051707.gct-oradb-demo-prd01-data-00 size:120.0 GB
name:gct-oradb-demo-dev01-data-01 id:ee320b80-0bec-5a70-5032-87565859e10f size:120.0
   is a target for gct-oradb-demo-prd01-pg.dec051707.gct-oradb-demo-prd01-data-01 size:120.0 GB
name:gct-oradb-demo-dev01-fra-00 id:173bdf4e-5d71-c89d-8e00-9746337999da size:40.0
   is a target for gct-oradb-demo-prd01-pg.dec051707.gct-oradb-demo-prd01-fra-00 size:40.0 GB
name:gct-oradb-demo-dev01-fra-01 id:d2680577-4c5f-f094-0a92-98f01e85c7a8 size:40.0
   is a target for gct-oradb-demo-prd01-pg.dec051707.gct-oradb-demo-prd01-fra-01 size:40.0 GB
============
determining volume mapping
nm:gct-oradb-demo-prd01-pg.dec051707.gct-oradb-demo-prd01-data-00 src id:a5abc4c3-f199-c026-7c97-a2468e4b5fda map:0 sz:120.0
  checking for tag matched volume
    volume gct-oradb-demo-prd01-pg.dec051707.gct-oradb-demo-prd01-data-00 will be synced to gct-oradb-demo-dev01-data-00
nm:gct-oradb-demo-prd01-pg.dec051707.gct-oradb-demo-prd01-data-01 src id:6c2937de-c30e-dde0-9613-fb15a06966b3 map:0 sz:120.0
  checking for tag matched volume
    volume gct-oradb-demo-prd01-pg.dec051707.gct-oradb-demo-prd01-data-01 will be synced to gct-oradb-demo-dev01-data-01
nm:gct-oradb-demo-prd01-pg.dec051707.gct-oradb-demo-prd01-fra-00 src id:cbda1d30-1313-4b3e-df61-f1fa35957ac3 map:0 sz:40.0
  checking for tag matched volume
    volume gct-oradb-demo-prd01-pg.dec051707.gct-oradb-demo-prd01-fra-00 will be synced to gct-oradb-demo-dev01-fra-00
nm:gct-oradb-demo-prd01-pg.dec051707.gct-oradb-demo-prd01-fra-01 src id:feabf082-e2ce-aaa5-b1ea-8adfd586a7c4 map:0 sz:40.0
  checking for tag matched volume
    volume gct-oradb-demo-prd01-pg.dec051707.gct-oradb-demo-prd01-fra-01 will be synced to gct-oradb-demo-dev01-fra-01
============
mapping the volumes
gct-oradb-demo-prd01-pg.dec051707.gct-oradb-demo-prd01-data-00 will be syncd to gct-oradb-demo-dev01-data-00
gct-oradb-demo-prd01-pg.dec051707.gct-oradb-demo-prd01-data-01 will be syncd to gct-oradb-demo-dev01-data-01
gct-oradb-demo-prd01-pg.dec051707.gct-oradb-demo-prd01-fra-00 will be syncd to gct-oradb-demo-dev01-fra-00
gct-oradb-demo-prd01-pg.dec051707.gct-oradb-demo-prd01-fra-01 will be syncd to gct-oradb-demo-dev01-fra-01
============
complete
</code>
