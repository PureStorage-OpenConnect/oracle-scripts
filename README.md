
![](graphics/purestorage.png)

# Pure Storage OpenConnect Oracle Scripts

# About this Repository
Welcome to the Oracle Pure Storage script repository. In this repository, you can access scripts written that allow Oracle DBAs to make the most of an Oracle database on Pure Storage.  Included here are scripts to create snapshots, full database clones, and replicate Oracle from one Flash Array to another.  Scripts are written in bash or Python.

# Business Application of Snapshots & Replication
Array-based snapshots are used to decouple database operations from the size of the data. Using array-based snapshots, you can accelerate access to data in several common database scenarios:

* Instant data + ransomware protection
* Dev/Test refreshes in seconds
* In-place application and database upgrades
* Intra-Instance ETL
* Offload database maintenance
* Offload RMAN backups
* Re-see a Dataguard Standby
* Read tags of an Oracle storage snapshot

# Technical Requirements
All scripts in this repository are designed for Linux.  Most will probably run on UNIX with minor modification.\
The shell scripts in this repository relies upon the purevol executable being installed locally.\
The Python code in this repository relies on [pypureclient Python library.](https://pypi.org/project/py-pure-client)\
Python code that interacts with Oracle also requires the [oracledb Python library.](https://pypi.org/project/oracledb)

# Sub Repositories
This repository contains several sub-directories:

* [bash](./bash/) - simple Linux bash scripts to clone an Oracle database on Pure Flash Array.
* [fa_pg_snap](./fa_pg_snap/) - Python script to snapshot and optionally clone a Pure Flash Array protection group.  (Not database aware).
* [fa_pg_ora_snap](./fa_pg_ora_snap) - Python script to snapshot and optionally clone an Oracle database using Pure Flash Array protection groups.

