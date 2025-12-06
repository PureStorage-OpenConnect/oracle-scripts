# Python scripts for snapshot and cloning a protection group on a Pure Flash Array

The script fa_pg_snap.py provides for taking a snapshot of a protection group on a Pure Flash Array.
It will also optionally copy that snapshot to a target protection group.  In this case the target protection group must have an equal or greater number of volumes of equal or larger size than the source.
The script can also copy an existing snapshot of a source protection group to a target protection group.
If replication is set up for the source protection group, the snapshot can be replicated to a second Flash Array.

# Arguments:

-s source protection group (required)\
-t target protection group (optional)\
-n the snapshot name.  If this does not exist - it will create it.  If it already exists, it will use the existing snapshot to sync to the target. (required)\
-f JSON file with FQDN and API token to connect to the Flash Arrays (required)\
-r replicate the snapshot to the targets specified in the source protection group (optional)\
-o output file with the names of the snapshot volumes (optional)\
-i ignore tag (optional - see below)\
-x execute Lock - if this is NOT set, no destructive actions will be taken.  Instead, the script will simply tell you would it would do.  This may prove useful to make sure you have all the settings right before you  overwrite a target protection group.\

# Notes:

If replication is not specified, both the source and target protection groups are assumed to be on the source Flash Array, and the target Flash Array is ignored.\
If the JSON file does not specify authentication credentials, the code will try to read the OS variables FA_HOST and API_TOKEN for authentication to the source Flash Array.\
If the JSON file does not specify authentication credentials, the code will try to read the OS variables FA_HOST_TGT and API_TOKEN_TGT for authentication to the target Flash Array.\

