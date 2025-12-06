# Python scripts for snapshot and cloning a protection group on a Pure Flash Array

The script fa_pg_snap.py provides for taking a snapshot of a protection group on a Pure Flash Array.
It will also optionally copy that snapshot to a target protection group.  In this case the target protection group must have an equal or greater number of volumes of equal or larger size than the source.
The script can also copy an existing snapshot of a source protection group to a target protection group.
If replication is set up for the source protection group, the snapshot can be replicated to a second Flash Array.

# Arguments:

-s source protection group (required)
-t target protection group (optional)
-n the snapshot name.  If this does not exist - it will create it.  If it already exists, it will use the existing snapshot to sync to the target. (required)
-f JSON file with credentials to connect to the Flash Array (required)
-r replicate the snapshot to the targets specified in the source protection group (optional)
-o output file with the names of the snapshot volumes (optional)
-i ignore tag (see below)
-x execute Lock - if this is left off, no destructive actions will be taken.  Rather the script will simply tell you would it would do.  Useful to make sure you have all the settings right before you actually sync a snapshot.

