## Demo python script to clone Oracle ASM diskgroups from ora1 and refresh the TARGETDB running on ora2
## Author : Danny Higgins
## Date : 03/08/2017
## Pre-Reqs : Requires purestorage package to interact with FlashArray API via python toolkit
##          : Requires cx_Oracle package to interact with database.
##          : some cx_Oracle calls required SYSDBA access via correctly configured password file
## Notes: change the oracle and flasharray authentication credentials as appropriate
##      : the cx_Oracle.connect method relies on a TNS connection which requires the database service being hardcoded in the listener.ora file


# Import security certifactes to avoid SSL warnings

import urllib3
urllib3.disable_warnings()

# Import the cx_Oracle module for database connectivity 

import cx_Oracle

# Set the oracle authentication details 

ora_source = cx_Oracle.connect('sys/sys123@10.219.225.101/SOURCEDB.puresg.com', mode = cx_Oracle.SYSDBA)
print ora_source.version
ora_source.close()

ora_target = cx_Oracle.connect('sys/sys123@10.219.225.102/TARGETDB.puresg.com', mode = cx_Oracle.SYSDBA)
print ora_target.version

asm_target = cx_Oracle.connect('sys/sys123@10.219.225.102/+ASM', mode = cx_Oracle.SYSASM)


# Import the purestorage module

import purestorage

# Set the array authentication details

array = purestorage.FlashArray("10.219.224.112", api_token="3bdf3b60-f0c0-fa8a-83c1-b794ba8f562c")

array_info = array.get()

print "FlashArray {} (version {}) REST session established!".format(array_info['array_name'], array_info['version'])

# SSH to array to snap source volume
print("About to take snaphot of SOURCEDB volumes using the python toolkit command...")
print("array.create_snapshots(['m_UCS_Oracle_ora1_RDM_CONTROL_REDO', 'm_UCS_Oracle_ora1_RDM_DATA'], suffix='REFRESH')")
inp = raw_input("Press return to continue: ")
snap_info = array.create_snapshots(["m_UCS_Oracle_ora1_RDM_CONTROL_REDO", "m_UCS_Oracle_ora1_RDM_DATA"], suffix="REFRESH")
print(snap_info)
#print "Snap {} of volume {} size {} bytes taken at {}".format(snap_info['source'], snap_info['name'], snap_info['size'])
# it's a list so need some loop?

    
# Shutdown target database
print("About to shutdown TARGETDB")
inp = raw_input("Press return to continue: ")
ora_target.shutdown(mode = cx_Oracle.DBSHUTDOWN_ABORT)
#ora_target.close()

print("About to unmount ASM disk groups +CONTROL_REDO & +DATA")
inp = raw_input("Press return to continue: ")

# Dismount +DATA & +CONTROL_REDO diskgroups
asm_cur = asm_target.cursor()
asm_cur.execute('alter diskgroup CONTROL_REDO dismount')
asm_cur.execute('alter diskgroup DATA dismount')      
    

# SSH to array to copy overwrite to the target volume
print("About to overwrite TARGETDB volumes using snaphot of SOURCEDB volumnes using the following commands")
print('array.copy_volume("m_UCS_Oracle_ora1_RDM_DATA.REFRESH", "m_UCS_Oracle_ora2_RDM_DATA", overwrite=True)')
print('array.copy_volume("m_UCS_Oracle_ora1_RDM_CONTROL_REDO.REFRESH", "m_UCS_Oracle_ora2_RDM_CONTROL_REDO", overwrite=True)')
inp = raw_input("Press return to continue: ")
copy_info = array.copy_volume("m_UCS_Oracle_ora1_RDM_DATA.REFRESH", "m_UCS_Oracle_ora2_RDM_DATA", overwrite=True)
print "volume {} of size {} bytes overwitten with snap of {}".format(copy_info['name'], copy_info['size'], copy_info['source'])
copy_info = array.copy_volume("m_UCS_Oracle_ora1_RDM_CONTROL_REDO.REFRESH", "m_UCS_Oracle_ora2_RDM_CONTROL_REDO", overwrite=True)   
print "volume {} of size {} bytes overwitten with snap of {}".format(copy_info['name'], copy_info['size'], copy_info['source'])

# Mount +DATA diskgroup
print("About to mount ASM disk groups +CONTROL_REDO & +DATA")
inp = raw_input("Press return to continue: ")
asm_cur.execute('alter diskgroup CONTROL_REDO mount force')
print("+CONTROL_REDO mounted")
asm_cur.execute('alter diskgroup DATA mount force') 
print("+DATA mounted")
asm_target.close()

# Start the database in MOUNT mode, add the DB_UNIQUE_NAME parameter to preserve the SID and then restart the database
print("About to mount SOURCEDB (this is an exact clone remember!!) and then rename it back to TARGETDB using alter system set db_unique_name='TARGETDB' scope=spfile;")
inp = raw_input("Press return to continue: ")
ora_target = cx_Oracle.connect('sys/sys123@10.219.225.102/TARGETDB.puresg.com', mode = cx_Oracle.SYSDBA | cx_Oracle.PRELIM_AUTH)
ora_target.startup()
ora_target = cx_Oracle.connect('sys/sys123@10.219.225.102/TARGETDB.puresg.com', mode = cx_Oracle.SYSDBA)
target_cur = ora_target.cursor()
target_cur.execute("alter database mount")
target_cur.execute("alter system set db_unique_name='TARGETDB' scope=spfile") 
ora_target.shutdown(mode = cx_Oracle.DBSHUTDOWN_ABORT)
ora_target = cx_Oracle.connect('sys/sys123@10.219.225.102/TARGETDB.puresg.com', mode = cx_Oracle.SYSDBA | cx_Oracle.PRELIM_AUTH)
ora_target.startup()
ora_target = cx_Oracle.connect('sys/sys123@10.219.225.102/TARGETDB.puresg.com', mode = cx_Oracle.SYSDBA)
target_cur = ora_target.cursor()
target_cur.execute("alter database mount")                   
target_cur.execute("alter database open")      
    

# Verify we have the lastest cut of data by selecting from the user data we inserted on the SOURCEDB
print("About to select from TARGETDB to check the user defined string we inserted into SOURCEDB is there")
inp = raw_input("Press return to continue: ")
target_cur.execute('SELECT * FROM CLONE_DEMO.UDATA')
for result in target_cur:
    print(result)
target_cur.close()    
ora_target.close()

# Cleanup the demo to avoid snapshot name conflice next time it's run - SSH to array to eradicate the snapshot
print("About to clean up the snapshots")
inp = raw_input("Press return to continue: ")

del_info = array.destroy_volume("m_UCS_Oracle_ora1_RDM_DATA.REFRESH")
print(del_info)
del_info = array.destroy_volume("m_UCS_Oracle_ora1_RDM_CONTROL_REDO.REFRESH")
print(del_info)                   
del_info = array.eradicate_volume("m_UCS_Oracle_ora1_RDM_DATA.REFRESH")
print(del_info)
del_info = array.eradicate_volume("m_UCS_Oracle_ora1_RDM_CONTROL_REDO.REFRESH") 
print(del_info)
      
# now end the pure session and invalidate the cookie

array.invalidate_cookie()