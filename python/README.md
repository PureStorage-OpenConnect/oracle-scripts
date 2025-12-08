
# Pure Storage OpenConnect Oracle Python Scripts 

# Technical Requirements
All scripts in this repository are designed for Linux.  Most will probably run on UNIX with minor modification.\
The Python code in this repository relies on [pypureclient Python library.](https://pypi.org/project/py-pure-client)\
Python code that interacts with Oracle also requires the [oracledb Python library.](https://pypi.org/project/oracledb)

# Sub Repositories
This repository contains several sub-directories:

* [fa_pg_snap](./fa_pg_snap/) - Python script to snapshot and optionally clone a Pure Flash Array protection group.  (Not database aware).
* [fa_pg_ora_snap](./fa_pg_ora_snap) - Python script to snapshot and optionally clone an Oracle database using Pure Flash Array protection groups.

