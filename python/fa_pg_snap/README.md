# Python scripts for snapshot and cloning a protection group on an Everpure Flash Array

The script fa_pg_snap.py provides for taking a snapshot of a protection group on an Everpure Flash Array.\
It will also optionally copy that snapshot to a target protection group.  In this case the target protection group must have an equal or greater number of volumes of equal size than the source.\
The script can also copy an existing snapshot of a source protection group to a target protection group.\
If replication is set up for the source protection group, the snapshot can be replicated to a second Flash Array.

# Requirements

- Python 3.8 or later
- py-pure-client (`python -m pip install py-pure-client`)
- `python -m pip install 'setuptools<72.0.0'`

# Arguments:

-s  source protection group (required unless `source_protection_group` is set in the JSON config file)\
-t  target protection group (optional - may also be set with `target_protection_group` in the JSON config file)\
-n  the snapshot name.  If this does not exist - it will create it.  If it already exists, it will use the existing snapshot to sync to the target. (required)\
-j  JSON file with FQDN and API token to connect to the Flash Arrays (optional - if omitted, connection details are read from environment variables, see Notes)\
-r  replicate the snapshot to the targets specified in the source protection group (optional - may also be set with `"replicate": "True"` in the JSON config file)\
-o  output file with the names of the snapshot volumes (optional)\
-i  ignore existing match (optional - see below)\
-x  execute lock - if this is NOT set, no destructive actions will be taken.  Instead, the script will simply tell you what it would do.  This may prove useful to make sure you have all the settings right before you overwrite a target protection group.

# JSON config file

The config file supports the following keys:

| Key | Purpose |
|---|---|
| `src_flash_array_host` (or `flash_array_host`) | FQDN of the source Flash Array |
| `src_flash_array_api_token` (or `flash_array_api_token`) | API token for the source Flash Array |
| `tgt_flash_array_host` | FQDN of the target Flash Array (replication only) |
| `tgt_flash_array_api_token` | API token for the target Flash Array (replication only) |
| `flash_array_api_version` | optional REST API version; auto-negotiated when omitted |
| `source_protection_group` (or `src_protection_group`) | source protection group, used when -s is not given |
| `target_protection_group` (or `tgt_protection_group`) | target protection group, used when -t is not given |
| `replicate` | `"True"` to replicate the snapshot, equivalent to -r |
| `excluded_volumes` | list of source volume IDs to exclude from the sync (see below) |

# Notes:

If replication is not specified, both the source and target protection groups are assumed to be on the source Flash Array, and the target Flash Array is ignored.\
If replication is specified, the script verifies that the source protection group has at least one replication target configured, and after creating the snapshot it waits for the transfer to complete (up to ten checks at five second intervals).\
Snapshots are tagged with a `replicate` tag recording whether they were created with replication. If -r is used against an existing snapshot, the script checks this tag and stops if the snapshot was not replicated when it was created.\
If the JSON file does not specify source authentication credentials, the code will try to read the OS variables PUREFA_URL and PUREFA_API for authentication to the source Flash Array.\
If the JSON file does not specify target authentication credentials, the code will try to read the OS variables PUREFA_TARGET_URL and PUREFA_TARGET_API for authentication to the target Flash Array.

# Excluding Volumes in the Protection Group

In some scenarios you may wish to exclude volumes from the snapshot-copy.  For example, RAC cluster disks might be included in the protection group to protect the source RAC cluster from failure or corruption, but you would not wish to overwrite RAC cluster disks on a target system if you were cloning the database to a new cluster. In this example, the JSON file allows the user to specify source volumes in the protection group that will NOT be sync'd to target volumes in the target protection group.

Excluded volumes are identified by their volume ID, supplied as a flat list of strings:

```
"excluded_volumes": [
    "dd246ff7-9104-71cd-0320-8915f47aa77e",
    "dd246ff7-9104-71cd-0320-8915f47aa77f"
]
```

# Source snapshot/target volume pairing

If a target protection group is specified, the code will overwrite the volumes of the target protection group with the contents of the source snapshot.\
To achieve this, the code first looks for a target volume that was tagged in a previous run as the pair for the source volume.  If no tagged pair exists, the code will look for an unmatched target volume of the same size.\
Volumes are considered in the order they are returned by the Flash Array, which is typically alphabetical, so if the same naming convention is used for both source and target, the volumes will be considered in order.  Once a suitable target has been identified, the code tags the volume of the target protection group with the volume id of the source volume.  This means that every subsequent execution of the code will see the same target volume overwritten from the same source snapshot volume.\
The -i flag may be used to ignore these tags and re-establish a new source-snapshot/target volume pairing, such as when the user decides to snapshot from a different source protection group.

# A Worked Example

In the example below, the source protection group oradb-prd01-pg is snapshot and then copied to the target protection group oradb-tst01-pg.\
The JSON file excludes two volumes from the snapshot/sync process.\


```
python fa_pg_snap.py -j json/prd01_2_tst01.remote.nodb.json -n nov051734 -x -r
============
fa_pg_snap.py 1.3.0 started at 2026-11-05 15:34:11.300240
============
connecting to Flash Array:array01.example.com API Version:2.44
connected
============
connecting to Flash Array:array02.example.com API Version:2.44
connected
============
determining if snapshot nov051734 exists for protection group:oradb-prd01-pg
source protection group:oradb-prd01-pg
target protection group:oradb-tst01-pg
============
querying the volumes for protection group:oradb-prd01-pg on array array01
oradb-prd01-data-00
oradb-prd01-data-01
oradb-prd01-fra-00
oradb-prd01-fra-01
============
creating snapshot for oradb-prd01-pg
============
============
listing the volumes for snapshot:nov051734
name:array01:oradb-prd01-pg.nov051734.oradb-prd01-data-00 sz:150.0 GB
name:array01:oradb-prd01-pg.nov051734.oradb-prd01-data-01 sz:150.0 GB
name:array01:oradb-prd01-pg.nov051734.oradb-prd01-fra-00 sz:40.0 GB
name:array01:oradb-prd01-pg.nov051734.oradb-prd01-fra-01 sz:40.0 GB
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
  is a target for array01:oradb-prd01-pg.nov051734.oradb-prd01-data-00
  sz:150.0 GB
nm:oradb-tst01-data-01
  id:bbbbbbbb-0000-0000-0000-000000000009
  is a target for array01:oradb-prd01-pg.nov051734.oradb-prd01-data-01
  sz:150.0 GB
nm:oradb-tst01-fra-00
  id:bbbbbbbb-0000-0000-0000-000000000010
  is a target for array01:oradb-prd01-pg.nov051734.oradb-prd01-fra-00
  sz:40.0 GB
nm:oradb-tst01-fra-01
  id:bbbbbbbb-0000-0000-0000-000000000011
  is a target for array01:oradb-prd01-pg.nov051734.oradb-prd01-fra-01
  sz:40.0 GB
============
determining volume mapping
nm:array01:oradb-prd01-pg.nov051734.oradb-prd01-data-00
  src id:bbbbbbbb-0000-0000-0000-000000000012 map:0
  sz:150.0 GB
  checking for tag matched volume
  will be synced to oradb-tst01-data-00
nm:array01:oradb-prd01-pg.nov051734.oradb-prd01-data-01
  src id:bbbbbbbb-0000-0000-0000-000000000013 map:0
  sz:150.0 GB
  checking for tag matched volume
  will be synced to oradb-tst01-data-01
nm:array01:oradb-prd01-pg.nov051734.oradb-prd01-fra-00
  src id:bbbbbbbb-0000-0000-0000-000000000014 map:0
  sz:40.0 GB
  checking for tag matched volume
  will be synced to oradb-tst01-fra-00
nm:array01:oradb-prd01-pg.nov051734.oradb-prd01-fra-01
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
array01:oradb-prd01-pg.nov051734.oradb-prd01-data-00
  src key:bbbbbbbb-0000-0000-0000-000000000012
  map:bbbbbbbb-0000-0000-0000-000000000008
  will be syncd to oradb-tst01-data-00
array01:oradb-prd01-pg.nov051734.oradb-prd01-data-01
  src key:bbbbbbbb-0000-0000-0000-000000000013
  map:bbbbbbbb-0000-0000-0000-000000000009
  will be syncd to oradb-tst01-data-01
array01:oradb-prd01-pg.nov051734.oradb-prd01-fra-00
  src key:bbbbbbbb-0000-0000-0000-000000000014
  map:bbbbbbbb-0000-0000-0000-000000000010
  will be syncd to oradb-tst01-fra-00
array01:oradb-prd01-pg.nov051734.oradb-prd01-fra-01
  src key:bbbbbbbb-0000-0000-0000-000000000015
  map:bbbbbbbb-0000-0000-0000-000000000011
  will be syncd to oradb-tst01-fra-01
============
complete


```
