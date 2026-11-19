
# Everpure Storage OpenConnect Oracle Python Scripts 

# Technical Requirements
All scripts in this repository are designed for Linux.  Most will probably run on UNIX with minor modification.\
The Python code in this repository relies on [pypureclient Python library.](https://pypi.org/project/py-pure-client)\
Python code that interacts with Oracle also requires the [oracledb Python library.](https://pypi.org/project/oracledb)

# Requirements

- Python 3.8 or later
- Purity 6.x or later
- py-pure-client (`python -m pip install py-pure-client`)
- `python -m pip install 'setuptools<72.0.0'`

# Sub Repositories
This repository contains several sub-directories:

* [fa_pg_snap](./fa_pg_snap/) - Python script to snapshot and optionally clone an Everpure Flash Array protection group.  (Not database aware).
* [fa_pg_ora_snap](./fa_pg_ora_snap) - Python script to snapshot and optionally clone an Oracle database using Pure Flash Array protection groups (requires fa_pg_snap).
* [fa_pg_ora_snap_rac](./fa_pg_ora_snap_rac) - Python script to snapshot and clone an Oracle database to/from remote servers including RAC clustered databases (requires fa_pg_snap and fa_pg_ora_snap).
* [fa_pod_cp](./fa_pod_cp/) - Python script to clone an NFS exported file system from an Everpure Flash Array (Not database aware).
* [clonedb2hosts](./clonedb2hosts/) - Older Python script to clone an Oracle database.  Many parameters are hard coded in the script.
