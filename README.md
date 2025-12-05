
![](https://raw.githubusercontent.com/PureStorage-OpenConnect/sqlserver-scripts/master/graphics/purestorage.png)

# Pure Storage OpenConnect Oracle Scripts

# About this Repository
Welcome to the Oracle Pure Storage script repository. In this repository, you can access scripts written that allow Oracle DBAs to make the most of an Oracle database on Pure Storage.  Included here are scripts to create snapshots, full database clones, and replicate Oracle from one Flash Array to another.  Scripts are written in bash or Python.

# Business Application of Snapshots & Replication
Array-based snapshots are used to decouple database operations from the size of the data. Using array-based snapshots, you can accelerate access to data in several common database scenarios:

* Instant data + ransomware protection
* Dev/Test refreshes in seconds

<ul>
<li>Instant data + ransomware protection</li>
<li>Dev/Test refreshes in seconds</li>
<li>In-place application and database upgrades</li>
<li>Intra-Instance ETL</li>
<li>Offload database maintenance</li>
<li>Offload RMAN backups</li>
<li>Re-see a Dataguard Standby</li>
<li>Read tags of an Oracle storage snapshot</li>
</ul>

# Technical Requirements
All scripts in this repository are designed for Linux.  Most will probably run on UNIX with minor modification.<br/>
The bash code in this repository relies upon the purevol executable being installed locally.<br/>
The Python code in this repository relies on pypureclient Python library.<br/>
Python code that interacts with Oracle also requires the oracledb Python library.<br/>

clonedb.sh - Script to clone single instance Oracle database mounted on filesystems

repSnap.sh - Script to refresh the target protection group with the latest snapshot from the source protection group
