# Python script for rapid cloning (snapshot) of a Pod containing one or more NFS exports on an Everpure Flash Array

The script fa_pod_cp.py provides for an instant clone of a Pod containing one or more NFS exported file systems on an Everpure Flash Array.\
The file systems in the cloned pod may optionally be re-exported and presented for hosts to use as read/writeable mounts.

# Requirements

- Python 3.8 or later
- Purity 6.x or later
- py-pure-client (`python -m pip install py-pure-client`)
- `python -m pip install 'setuptools<72.0.0'`

# Arguments:

-s  source pod name (must exist on the Flash Array) (required).\
-t  target pod name (must NOT exist on the Flash Array) (required).\
-a  suffix to be appended to the cloned exported file systems. (optional - if omitted the cloned file systems will not be exported).\
-j  JSON file with FQDN and API token to connect to the Flash Arrays (optional - if omitted, connection details are read from environment variables, see Notes)\
-x  execute lock - if this is NOT set, no destructive actions will be taken.  Instead, the script will simply tell you what it would do.

# JSON config file

The config file supports the following keys:

| Key | Purpose |
|---|---|
| `src_flash_array_host` (or `flash_array_host`) | FQDN of the source Flash Array |
| `src_flash_array_api_token` (or `flash_array_api_token`) | API token for the source Flash Array |
| `flash_array_api_version` | optional REST API version; auto-negotiated when omitted |
| `rules` | export rules to apply to the cloned file systems.  If omitted the source pod's rules and policies will be cloned  |


# Notes:

If the JSON file does not specify target authentication credentials, the code will try to read the OS variables PUREFA_URL and PUREFA_API for authentication to the target Flash Array.

# Changing Rules and Policies.

The script allows for the cloned file systems to be exported using the suffix (-a) specified on the command line.\
An example is shown below:

```
   "rules": [
      {
         "access": "no-root-squash",
         "client": "10.20.30.71",
         "permission": "rw",
         "nfs_version": "NFSv3,NFSv4"
      }
   ]
```

In our example, we have restricted client access to 10.20.30.71.  The exported file systems are exported as NFS v3 and NFS v4.1 shares, and permissions are set to r/w.


# A Worked Example

In the example below, the pod gct-oradb-swingdb-pod which contains two exported file systems: gct-fs-ora-swingdb-data and gct-fs-ora-swingdb-fra are cloned, with the clones being exported as gct-fs-ora-swingdb-data-clone and gct-fs-ora-swingdb-fra-clone.\
The JSON file changes the export rules and policies.\
Once complete, authorized clients will be able to mount the cloned file systems as NFS shares.\


```
$ python fa_pod_cp.py -j json/nfs.json -s gct-oradb-swingdb-pod -t gct-pod-tmp -a=-clone -x
============
fa_pod_cp.py 1.3.0 started at 2026-11-18 10:50:09.145402
============
connecting to Flash Array:myflasharray.purestorage.com API Version:2.44
connected
============
cloning pod gct-oradb-swingdb-pod to gct-pod-tmp
============
checking for existence of source-pod and non-existence of target-pod
============
determining relevant policies for gct-oradb-swingdb-pod
policy gct-oradb-swingdb-pod::gct-oradb-nfs-pol
number of policies found:1
============
determining client rules for NFS policies for gct-oradb-swingdb-pod
rules for policy:gct-oradb-swingdb-pod::gct-oradb-nfs-pol
4 rule(s) found
============
checking that target export directories can be created
============
determining file systems for gct-oradb-swingdb-pod
file system gct-oradb-swingdb-pod::gct-fs-ora-swingdb-data
file system gct-oradb-swingdb-pod::gct-fs-ora-swingdb-fra
number of source pod file systems found:2
============
cloning pod gct-oradb-swingdb-pod to gct-pod-tmp
============
cloning policies for gct-pod-tmp
cloning policy gct-oradb-swingdb-pod::gct-oradb-nfs-pol as gct-pod-tmp::gct-oradb-nfs-pol
============
getting directory exports for gct-oradb-swingdb-pod
clone of gct-nfs-ora-swingdb-fra exported as gct-nfs-ora-swingdb-fra-clone
clone of gct-nfs-ora-swingdb-data exported as gct-nfs-ora-swingdb-data-clone
============
pod cloning complete

```
