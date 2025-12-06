# Python scripts for snapshot and cloning an Oracle database on Pure Flash Array

The script fa_pg_snap.py provides for taking a snapshot of a protection group on a Pure Flash Array.\
It will also optionally copy that snapshot to a target protection group.  In this case the target protection group must have an equal or greater number of volumes of equal or larger size than the source.\
The script can also copy an existing snapshot of a source protection group to a target protection group.\
If replication is set up for the source protection group, the snapshot can be replicated to a second Flash Array.

# Requirements:

This Python code imports the fa_pg_snap.py code.

# Arguments:

-s source protection group (required)\
-t target protection group (optional)\
-n the snapshot name.  If this does not exist - it will create it.  If it already exists, it will use the existing snapshot to sync to the target. (required)\
-f JSON file with FQDN and API token to connect to the Flash Arrays (required)\
-r replicate the snapshot to the targets specified in the source protection group (optional)\
-o output file with the names of the snapshot volumes (optional)\
-i ignore tag (optional - see below)\
-b use oracle backup mode (optional - defaults to no) 
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
