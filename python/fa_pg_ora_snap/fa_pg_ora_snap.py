#
# Python script to snapshot an Oracle database and optionally re-sync to a target PG
#
# Graham Thornton - Sep 2025
# gthornton@purestorage.com
#
# requires py_pure_client
# requires python -m pip install 'setuptools<72.0.0'
# requires python -m pip install oracledb
# requires fa_pg_snap
#
# usage:
# python fa_pg_ora_snap.py -s gct-oradb-vvol-ac::pgroup-auto -t gct-oradb-vvol-pg-swingtarget -n gct1 -f config.json -x
#

import sys
import time
import os
import re
import datetime
import json
import argparse
import oracledb
import getpass

import warnings
warnings.filterwarnings(action='ignore')

from pypureclient import flasharray
import urllib3

#
# this script builds upon fa_pg_snap
#
import fa_pg_snap

# global variables
halt=1
nohalt=0
version = "1.9.0"
not_defined = "Not Defined"
ora_bBackupMode = False

lst_db_parameters = ['control_files','db_recovery_file_dest','db_recovery_file_dest_size','enable_pluggable_database']

# disable the HTTPS warnings
urllib3.disable_warnings()

# store values read from the database and then written as tags
dictDBParams={}


##############################################

# FLASH ARRAY

##############################################

def mTagSnapshot( my_array, my_snapshot_exists, my_vols, my_protection_group, my_snapshot_name, my_safe_mode, my_remote ):

    def fWriteSnapshotTag( my_array, lst_vols, my_protection_group, my_snapshot_name, my_tag_key, my_tag_val, my_vvol, my_remote ):

        count=0

        print( f'tagging the snapshot: key:{my_tag_key} val:{my_tag_val}' )

        # get a list of snapshots for the protection group volumes
        # on a replicated target we would need to prefix the array name
        # so we just grab all of the snapshot volumes
        response = my_array.get_volume_snapshots( source_names=lst_vols )
        if( my_remote ): response = my_array.get_volume_snapshots( )

        for myoutput in response.items:

            # check against each volume of each snapshot
            for volume_name in lst_vols:

                #
                # if the volume is a vvol, the volume_name is prefixed with the vvol name
                # this is not included in the snapshot name
                # so we remove it here for the purposes of matching
                # the removal is everything before the second colon
                #
                if my_vvol: volume_name = re.sub(r"^[^:]*:[^:]*:", "", volume_name)

                match = str(my_protection_group)+'.'+str(my_snapshot_name)+'.'+volume_name

                # is this volume part of our snapshot?
                if myoutput.name.endswith(match):
                
                    count+=1
  
                    kv={
                        'key': my_tag_key,
                        'value': my_tag_val,
                        'copyable': True,
                    }

                    # tagging
                    try:
                        response2 = my_array.put_volume_snapshots_tags_batch( resource_names=[myoutput.name], tag=[kv] )

                    except:
                        fa_pg_snap.mError( halt, 0, 'call to put_volume_snapshots_tags_batch failed' )

                    if ( response2.status_code != 200 ): fa_pg_snap.mError( halt, response2.status_code, response2.errors[0].message )

        return count

    def fReadSnapshotTag( my_array, lst_vols, my_protection_group, my_snapshot_name, my_tag_key, my_vvol, my_remote ):

        count=0

        # get a list of snapshots for the protection group volumes
        # on a replicated target we would need to prefix the array name
        # so we just grab all of the snapshot volumes
        response = my_array.get_volume_snapshots( source_names=lst_vols )
        if( my_remote ): response = my_array.get_volume_snapshots( )

        for myoutput in response.items:

            # check against each volume of each snapshot
            for volume_name in lst_vols:

                #
                # if the volume is a vvol, the volume_name is prefixed with the vvol name
                # this is not included in the snapshot name
                # so we remove it here for the purposes of matching
                # the removal is everything before the second colon
                #
                if my_vvol: volume_name = re.sub(r"^[^:]*:[^:]*:", "", volume_name)

                match = str(my_protection_group)+'.'+str(my_snapshot_name)+'.'+volume_name

                # is this volume part of our snapshot?
                if myoutput.name.endswith(match):

                    count+=1

                    try:
                        response = my_array.get_volume_snapshots_tags( resource_names=[myoutput.name] )
                    except:
                        fa_pg_snap.mError( halt, 0, 'call to get_volume_snapshots_tags failed' )

                    if ( response.status_code != 200 ): fa_pg_snap.mError( halt, response.status_code, response.errors[0].message )

                    #print( response )
                    for item in response.items:

                        if( item.key == my_tag_key ):
 
                            dictDBParams.update({ item.key:item.value })

                            if( count==1 ): print( f'reading tag from snapshot {item.key}:{item.value}' )

        return count

    print( '============' )
    lst_tag_keys = ['db_name','db_id','db_time','db_unique_name','db_role','db_open_mode','archivelog_mode','flashback_mode','platform_name','encrypted_tablespaces','version','backup_mode','control_files','db_recovery_file_dest','db_recovery_file_dest_size','enable_pluggable_database','asm_disk_groups','open_pdbs']

    for tag_key in lst_tag_keys:

        if( my_snapshot_exists ): 

            matched = fReadSnapshotTag( my_array, my_vols, my_protection_group, my_snapshot_name, tag_key, False, my_remote )

            if (matched==0): fReadSnapshotTag( my_array, my_vols, my_protection_group, my_snapshot_name, tag_key, True, my_remote )

        else:

            # dont tag a snapshot if we are in safe mode
            if( my_safe_mode ): break

            tag_val=str(dictDBParams.get( tag_key, not_defined ))
            matched = fWriteSnapshotTag( my_array, my_vols, my_protection_group, my_snapshot_name, tag_key, tag_val, False, my_remote )

            if (matched==0): fWriteSnapshotTag( my_array, my_vols, my_protection_group, my_snapshot_name, tag_key, tag_val, True, my_remote )




##############################################

# ORACLE

##############################################

#
# connect to an Oracle database and return the connection handle
#
def fOracleConnect( myusr, mypwd, mycs ):

    try:
        myconn = oracledb.connect(user=myusr, password=mypwd, dsn=mycs, mode=oracledb.SYSDBA)

    except oracledb.Error as e:

        fa_pg_snap.mQuit("Oracle Connection Error:"+str(e))

    return myconn

#
# execute the sql statement
#
def mSQLExecute( myconn, mystmt ):

    try:

        with myconn.cursor() as cursor: cursor.execute( mystmt )

    except oracledb.Error as e:

        fa_pg_snap.mQuit("Oracle Error:"+str(e))

#
# execute the sql statement and return a list of results
#
def fSQLExecuteList( myconn, mystmt ):

    lst_result=[]

    try:

        cursor = myconn.cursor()
        cursor.execute(mystmt)
        rows = cursor.fetchall()

        # convert the list of tuples to a list of lists
        list_of_lists = [list(row) for row in rows]

        # add the result to the result set
        for row in list_of_lists: lst_result.append( str(row[0]) )

    except oracledb.Error as e:

        fa_pg_snap.mQuit("Oracle Error:"+str(e))

    return lst_result

#
# execute the sql statement and return the list of rows as a single CSV line
#
def fSQLExecute( myconn, mystmt ):

    my_list=fSQLExecuteList( myconn, mystmt )

    try:
     
        return re.sub(r'[\n\r]+', ',', ",".join(my_list))

    except:

        return ""

#
# connect to sqlplus and execute the list of commands
# return any result as a list
#

def fOraLocalExecute( sid, home, cs, lst_mystmts ):

    lst_result=[]

    os.environ["ORACLE_SID"]=sid
    os.environ["ORACLE_HOME"]=home

    tmp_output_file = os.getcwd()+"/ora_"+str(os.getpid())+".tmp"
    err_output_file = os.getcwd()+"/ora_"+str(os.getpid())+".err"

    process = os.popen("$ORACLE_HOME/bin/sqlplus -s /nolog >> "+err_output_file+" 2>&1", "w" )
    process.write( cs+"\n" )

    lst_format=["set echo off","set term off","set verify off","set pagesize 999","set linesize 300","set feedback off","set trimspool on","set heading off"]
    for cmd in lst_format:
        #print( cmd )
        process.write( cmd+"\n" )

    cmd = "spool "+tmp_output_file
    process.write( cmd+"\n" )

    for cmd in lst_mystmts:
        #print( cmd )
        process.write( cmd+"\n" )

    process.write( "spool off\n" )
    process.write( "exit\n" )
    process.close()

    file = open(tmp_output_file, 'r')
    lines = file.readlines()
    for line in lines:
        clean_line = line.strip()
        if len( clean_line )>0: lst_result.append( line.strip() )
    file.close()

    os.remove( tmp_output_file )
    os.remove( err_output_file )

    return lst_result

#
# query if any of the ASM diskgroups are mounted
#

def fQueryASMDGMounted( asm_sid, asm_home, lst_source_asm_dg ):

    lst_result=[]

    if len( lst_source_asm_dg ) >0:

        lst_output = fOraLocalExecute( asm_sid, asm_home, "connect / as sysasm", ["select name from v$asm_diskgroup where state ='MOUNTED';"] )

        for source_asm_dg in lst_source_asm_dg:

            if( source_asm_dg in lst_output ):
                print( "ASM diskgroup "+source_asm_dg+" is mounted on the target" )
                lst_result.append( source_asm_dg )
            else:
                print( "ASM diskgroup "+source_asm_dg+" is not mounted on target" )

    return( lst_result )

#
# determine if the target instance is running
#
def fQueryTargetInstanceRunning( ora_sid, ora_home ):

    lst_output = fOraLocalExecute( ora_sid, ora_home, "connect / as sysdba", ["select status from v$instance;"] )

    if( "ORA-01034: ORACLE not available" in lst_output ):
        return( "DOWN" )

    return ( str( lst_output[0] ) )

#
# mount ASM diskgroups on the target
#

def mMountASMDG( asm_sid, asm_home, lst_source_asm_dg ):

    lst_commands=[]

    if len( lst_source_asm_dg ) >0:

        # mount the asm diskgroups
        for source_asm_dg in lst_source_asm_dg:

            print( "mounting diskgroup "+source_asm_dg )
            lst_commands.append( 'alter diskgroup '+source_asm_dg+' mount;' )

        myres = fOraLocalExecute( asm_sid, asm_home, "connect / as sysasm", lst_commands )

#
# start the target instance to the required state
#

def mOraStartTarget( ora_sid, ora_home, ora_target_mode, ora_backup_mode ):

    if ora_target_mode=="DOWN": return

    cmd_list=["startup nomount;"]

    if ora_target_mode=="MOUNTED" or ora_target_mode=="OPEN":

        cmd_list.append( "alter database mount;" )

        if ora_backup_mode: cmd_list.append( "alter database end backup;" )

    if ora_target_mode=="OPEN": cmd_list.append( "alter database open;" )

    #print( cmd_list )

    myres = fOraLocalExecute( ora_sid, ora_home, "connect / as sysdba", cmd_list )

#
# open pluggable databases
#

def mOraStartPluggable( ora_sid, ora_home, ora_target_mode ):

    if ora_target_mode!="OPEN": return

    cmd_list = []

    open_pdbs = dictDBParams.get( 'open_pdbs', not_defined )

    local_listener  = fa_pg_snap.dictArgs.get( 'local_listener', "" )

    if( open_pdbs == not_defined ):
        print( 'no pluggable databases to re-open' )
        return

    for open_pdb in open_pdbs.split(','):

        print( 'opening '+str(open_pdb))
        cmd_list.append( "alter pluggable database "+str(open_pdb)+" open;" )
        cmd_list.append( "alter session set container="+str(open_pdb)+";" )
        cmd_list.append( "alter system set local_listener='"+local_listener+"';" )
        cmd_list.append( "alter system register;" )
        cmd_list.append( "connect / as sysdba" )

        #print( str(cmd_list))

    myres = fOraLocalExecute( ora_sid, ora_home, "connect / as sysdba", cmd_list )

#
# reset the SPFILE of the target database
#
def mOraResetTargetSPFILE( ora_sid, ora_home ):

    print( 'resetting the target SPFILE' )

    cmd_list = []

    # reset the database name
    value = dictDBParams.get( 'db_name' )
    cmd = "alter system set db_name='"+value+"' sid='*' scope=spfile;"
    cmd_list.append( cmd )
    print( cmd )

    for parameter in lst_db_parameters:

        value = dictDBParams.get( parameter )

        if( parameter=='control_files' ):
            value = "'"+re.sub(r", ", "','", value )+"'"

        if( parameter=='db_recovery_file_dest' ):
            value = "'"+value+"'"

        cmd = "alter system set "+parameter+"="+value+" sid='*' scope=spfile;"
        cmd_list.append( cmd )
        print( cmd )

    # see if db_unique_name is defined - if so add it to the list of parameters to reset in the target spfile file
    db_unique_name = fa_pg_snap.dictArgs.get( 'db_unique_name', not_defined ) 
    if( db_unique_name != not_defined ): 
        cmd = "alter system set db_unique_name="+db_unique_name+" sid='*' scope=spfile;"
        cmd_list.append( cmd )
        print( cmd )

    # we need to bounce the instance to re-read the spfile
    print( 'restarting instance' )
    cmd_list.append( 'shutdown immediate' );

    fOraLocalExecute( ora_sid, ora_home, "connect / as sysdba", cmd_list )

#
# connect to the source database
# read the source database settings and optionally put it into backup mode
#
def fOraSourceConnect( my_source_snapshot_exists, my_backup_mode ):

    #
    # connect to the source database - if defined
    #
    un = fa_pg_snap.dictArgs.get( "ora_src_usr", not_defined )
    cs = fa_pg_snap.dictArgs.get( "ora_src_cs", not_defined )
    pw = fa_pg_snap.dictArgs.get( "ora_src_pwd", not_defined )

    my_db_conn = None

    if( ( not my_source_snapshot_exists ) and un != not_defined and pw != not_defined and cs != not_defined ):

        print( '============' )
        print( "connecting to source database:"+cs )
        my_db_conn = fOracleConnect( un, pw, cs )

        print( f'use backup mode:{my_backup_mode}' )
        dictDBParams.update({ "backup_mode": ("Yes" if my_backup_mode else "No")})

        print( '============' )
        print( 'reading source database settings' )

        # get the asm dg list from the source database
        sql = "select name from v$asm_diskgroup where state='CONNECTED'"
        my_result = fSQLExecute( my_db_conn, sql )
        dictDBParams.update({ "asm_disk_groups": my_result })
        print( f'asm diskgroups: {my_result}' )

        # get the database name
        sql = "select name from v$database"
        my_result = fSQLExecute( my_db_conn, sql )
        dictDBParams.update({ "db_name": my_result })
        print( f'database name: {my_result}' )

        # get the database id
        sql = "select dbid from v$database"
        my_result = fSQLExecute( my_db_conn, sql )
        dictDBParams.update({ "db_id": my_result })
        print( f'database id: {my_result}' )

        # get the database time
        sql = "select to_char(sysdate,'YYYY/MM/DD HH24:MI:SS') from v$database"
        my_result = fSQLExecute( my_db_conn, sql )
        dictDBParams.update({ "db_time": my_result })
        print( f'database time: {my_result}' )

        # get the database unique name
        sql = "select db_unique_name from v$database"
        my_result = fSQLExecute( my_db_conn, sql )
        dictDBParams.update({ "db_unique_name": my_result })

        # get the database open mode
        sql = "select open_mode from v$database"
        my_db_open_mode = fSQLExecute( my_db_conn, sql )
        dictDBParams.update({ "db_open_mode": my_db_open_mode })
        print( f'database open mode: {my_db_open_mode}' )

        # get the database role
        sql = "select database_role from v$database"
        my_db_role = fSQLExecute( my_db_conn, sql )
        dictDBParams.update({ "db_role": my_db_role })
        print( f'database role: {my_db_role}' )

        # we can only read DBA_TABLESPACES if the source is open
        my_result=0
        if( my_db_open_mode == 'READ WRITE' and my_db_role == 'PRIMARY' ):
            # how many tablespaces are encrypted
            sql = "select count(*) from dba_tablespaces where upper(encrypted)!='NO'"
            my_result = fSQLExecute( my_db_conn, sql )
        dictDBParams.update({ "encrypted_tablespaces": my_result })
        print( f'encrypted tablespaces: {my_result}' )

        # get the archivelog mode
        sql = "select log_mode from v$database"
        my_result = fSQLExecute( my_db_conn, sql )
        dictDBParams.update({ "archivelog_mode": my_result })
        print( f'archivelog mode: {my_result}' )

        # get the flashback mode
        sql = "select flashback_on from v$database"
        my_result = fSQLExecute( my_db_conn, sql )
        dictDBParams.update({ "flashback_mode": my_result })
        print( f'flashback mode: {my_result}' )

        # get the platform
        sql = "select platform_name from v$database"
        my_result = fSQLExecute( my_db_conn, sql )
        dictDBParams.update({ "platform_name": my_result })
        print( f'platform name: {my_result}' )

        # get the version
        sql = "select banner_full from v$version"
        my_result = fSQLExecute( my_db_conn, sql )
        dictDBParams.update({ "version": my_result })
        print( f'version: {my_result}' )

        # gather parameter information
        for parameter in lst_db_parameters:
            sql = "select value from v$parameter where name = '"+parameter+"'"
            my_result = fSQLExecute( my_db_conn, sql )
            dictDBParams.update({ parameter: my_result })
            print( f'{parameter}: {my_result}' )

        #for r in lst_result: print( r )

        # if we are a container database....
        myres = dictDBParams.get( 'enable_pluggable_database', [] )
        if( str(myres)=='TRUE' ):

            # get the open pluggable databases
            print( 'identifying the open pluggable databases' )

            sql = "select name from v$pdbs where open_mode='READ WRITE'"
            my_result = fSQLExecute( my_db_conn, sql )

            if( len( my_result )==0 ):
                print( 'no open pluggable databases found' )

            else:
                print( f'open pdbs: {my_result}' )
                dictDBParams.update({ "open_pdbs": my_result })


        # begin backup mode if we need to make a snapshot and we want backup mode
        if( not my_source_snapshot_exists and my_backup_mode ):

            print( '============' )
            print( 'source db begin backup mode' )
            mSQLExecute( my_db_conn, "alter database begin backup" )
    

    return my_db_conn

##############################################

# MAIN BLOCK

##############################################

def doMain( ):

    # parse the command line args
    parser = argparse.ArgumentParser(
                    prog='fa_pg_ora_snap ', usage='%(prog)s [-s -t -n -f -i -r -b -o -x -h]',
                    description='snapshot an oracle database on a Pure Flash Array',
                    epilog='coded by Graham Thornton - gthornton@purestorage.com')

    parser.add_argument('-s','--source_protection_group', help='source pg', required=False)
    parser.add_argument('-t','--target_protection_group', help='target pg', required=False)
    parser.add_argument('-n','--snapshot_name', help='name of the snapshot', required=True)
    parser.add_argument('-o','--open_mode', help='requested state of the target instance (down, started, mounted, open)', required=False)
    parser.add_argument('-f','--config_file', help='json document of config options', required=True)
    parser.add_argument('-i','--ignore_match', action='store_true', help='ignore tag-matching')
    parser.add_argument('-r','--replicate', action='store_true', help='replicate the snapshot')
    parser.add_argument('-b','--backup_mode', action='store_true', help='put source database into backup mode')
    parser.add_argument('-x','--execute_lock', action='store_false', help="specify -x to actually snap the database (default is safety lock on)")

    args = parser.parse_args()


    print( '============' )
    print( f'fa_pg_ora_snap.py {version} started at {datetime.datetime.now()}' )

    caSnapshotName=args.snapshot_name
    bSourceSnapshotExists=False

    #
    # read the config file
    #
    if( args.config_file != None ): fa_pg_snap.dictArgs = fa_pg_snap.fReadConnectionJSON( args.config_file )

    # fa variables for source array
    src_flash_array = fa_pg_snap.dictArgs.get( "src_flash_array_host", os.environ.get('FA_HOST') )
    src_flash_array_api_token = fa_pg_snap.dictArgs.get( "src_flash_array_api_token", os.environ.get('API_TOKEN') )

    if( src_flash_array==None or src_flash_array_api_token==None ):
        fa_pg_snap.mQuit( 'src_flash_array_host and src_flash_array_api_token need to be defined in the config file or environment variables' )

    #
    # connect to the source FA
    #
    myArraySrc = fa_pg_snap.fFAConnect( src_flash_array, src_flash_array_api_token )
    src_array_name = fa_pg_snap.fFAQueryName( myArraySrc )

    #
    # do we want to replicate this snapshot?
    #
    if( args.replicate ):

        # fa variables for target array
        tgt_flash_array = fa_pg_snap.dictArgs.get( "tgt_flash_array_host", os.environ.get('FA_HOST_TGT') )
        tgt_flash_array_api_token = fa_pg_snap.dictArgs.get( "tgt_flash_array_api_token", os.environ.get('API_TOKEN_TGT') )

        if( tgt_flash_array==None or tgt_flash_array_api_token==None ):
            fa_pg_snap.mQuit( 'tgt_flash_array_host and tgt_flash_array_api_token need to be defined in the config file or environment variables' )

        #
        # connect to the target FA
        #
        myArrayTgt = fa_pg_snap.fFAConnect( tgt_flash_array, tgt_flash_array_api_token )
        tgt_array_name = fa_pg_snap.fFAQueryName( myArrayTgt )

    else:

        myArrayTgt = myArraySrc    
        tgt_array_name = src_array_name


    #
    # get the source and optional target protection groups
    #
    caSourceProtectionGroup=fa_pg_snap.fNotNone( args.source_protection_group, fa_pg_snap.dictArgs.get ( "source_protection_group", not_defined ))
    caTargetProtectionGroup=fa_pg_snap.fNotNone( args.target_protection_group, fa_pg_snap.dictArgs.get ( "target_protection_group", not_defined ))


    #
    # check if the source pg has the requested snapshot
    #

    bSourceSnapshotExists=fa_pg_snap.fQuerySnapExists( myArraySrc, caSnapshotName, caSourceProtectionGroup )

    print( f'source protection group:{caSourceProtectionGroup}' )
    print( f'target protection group:{caTargetProtectionGroup}' )

    #
    # oracle target/local variables
    #
    ora_sid = fa_pg_snap.dictArgs.get( "oracle_sid", not_defined )
    ora_home = fa_pg_snap.dictArgs.get( "oracle_home", not_defined )

    ora_target_mode = fa_pg_snap.fNotNone( args.open_mode, fa_pg_snap.dictArgs.get( "oracle_target_mode", "DOWN" ))
    ora_target_mode = ora_target_mode.upper()

    if( ora_target_mode.upper() not in ['DOWN','STARTED','MOUNTED','OPEN']):
        fa_pg_snap.mQuit( "target database mode must be DOWN, STARTED, MOUNTED or OPEN" )

    if( ora_sid != not_defined and ora_home != not_defined ):
        print( '============' )
        print( "setting local oracle sid and home" )
        os.environ["ORACLE_SID"]=ora_sid
        os.environ["ORACLE_HOME"]=ora_home

    # check if we want oracle backup mode used
    bBackupMode = fa_pg_snap.fDictBool( "ora_backup_mode", False )
    bBackupMode = ( bBackupMode | bool(args.backup_mode) )

    # get the target ASM instance details
    asm_sid = fa_pg_snap.dictArgs.get( "asm_sid", not_defined )
    asm_home = fa_pg_snap.dictArgs.get( "asm_home", not_defined )


    # connect to the source, read v$parameter and put it into backup mode
    dbSourceConnection = fOraSourceConnect( bSourceSnapshotExists, bBackupMode )


    #
    # if the snapshot does not exist create it
    # if safety lock engaged this will return a null string
    #

    if( not bSourceSnapshotExists ): caSnapshotName=fa_pg_snap.fCreateSnapshot( myArraySrc, args.execute_lock, caSnapshotName, caSourceProtectionGroup, args.replicate, None )


    #
    # come out of backup mode
    # if we have a source db connection, we made a snapshot and we wanted backup mode
    #

    if ( not bSourceSnapshotExists and dbSourceConnection != None and bBackupMode ):

        print( '============' )
        print( 'source db end backup mode' )
        mSQLExecute( dbSourceConnection, "alter database end backup" )



    #
    # query the volumes of the source pg
    # these are collected in lst_source_vols
    #
    lstSourceVols = fa_pg_snap.fQueryVolsinPG( myArraySrc, caSourceProtectionGroup )



    #
    # tag the snapshot volumes with all of the key values read from the source database
    #
    mTagSnapshot( myArraySrc, bSourceSnapshotExists, lstSourceVols, caSourceProtectionGroup, caSnapshotName, args.execute_lock, False )

    #
    # get any excluded volumes - RAC cluster disks and VVOL config volumes need to be excluded
    #
    print( '============' )
    print( 'excluded volumes' )
    lstExcludedVols = fa_pg_snap.dictArgs.get( "excluded_volumes", [] )
    for vol in lstExcludedVols: print ( f'excluding:{vol}' )



    #
    # query the snapshots of the volumes in the source pg
    # these are recorded in fa_pg_snap.dictSourceVols( id:target_map|vol_name|size_in_bytes )
    # entries found in the exclude file will be omitted
    #
    nSnapshotVols = fa_pg_snap.fQueryVolumesinSnapshot( myArrayTgt, caSourceProtectionGroup, caSnapshotName, lstSourceVols, lstExcludedVols )

    #
    # if not target PG was define we stop here
    #
    if caTargetProtectionGroup==not_defined: fa_pg_snap.mQuit( )


    #
    # determine if target database is running
    #
    print( '============'  )
    print( f'determining if target instance {ora_sid} is running' )

    caTargetOraStatus = fQueryTargetInstanceRunning( ora_sid, ora_home )

    if( caTargetOraStatus.upper() != "DOWN" ): fa_pg_snap.mQuit( 'target instance is running' )

    print( 'target instance is not running ')

    #
    # call ASM to determine what diskgroups are online
    #
    if( asm_sid != not_defined and asm_home != not_defined ):

        print( '============'  )
        print( "determining if target ASM diskgroups are mounted" )

        source_asm_dg = dictDBParams.get( "asm_disk_groups", "" )
        lstMountedDGs = fQueryASMDGMounted( asm_sid, asm_home, source_asm_dg.split(',') )

        if( len( lstMountedDGs )>0 ): fa_pg_snap.mQuit( str( len( lstMountedDGs ))+' ASM diskgroup(s) are still mounted on the target' )

    #
    # query the volumes of the target pg
    # collect these in lstTargetVols
    #
    lstTargetVols = fa_pg_snap.fQueryVolsinPG( myArrayTgt, caTargetProtectionGroup )


    #
    # verify the target PG has enough volumes to sync with the source snapshot
    #
    if( nSnapshotVols > len( lstTargetVols )):
        fa_pg_snap.mQuit( 'snapshot '+caSnapshotName+' has '+str(nSnapshotVols)+' volumes, but the target protection group only has '+str(len( lstTargetVols )))


    #
    # for each target volume get the capacity and the source volume id
    # this call populates fa_pg_snap.dictTargetVols id:source_map|vol_name|size
    #
    fa_pg_snap.mQueryTargetVolumeDetails( myArrayTgt, args.ignore_match, lstTargetVols )


    #
    # process the source volume dictionary and see if there are suitable matches in the target volume dictionary
    # we process the dictSource looking for volumes where the tmap is not set
    # we then look for a match in dictTarget
    # when found we update dictSource tmap
    # 
    nUnmatched = fa_pg_snap.fCreateVolumeMap( )

    if( nUnmatched>0 ):
        fa_pg_snap.mQuit( str(nUnmatched)+' volumes were unmatched' )



    #
    # check if this snapshot is to be replicated
    #
    if( args.replicate and not bSourceSnapshotExists ):

        retval = fa_pg_snap.fQuerySnapshotReplication( myArrayTgt, src_array_name, caSourceProtectionGroup, caSnapshotName, 10, 5, args.execute_lock )
        if( retval==False ):
            mError( halt, 0, 'snapshot replication did not complete in the time allowed' )

        mTagSnapshot( myArrayTgt, bSourceSnapshotExists, lstSourceVols, caSourceProtectionGroup, caSnapshotName, args.execute_lock, True )
    

    #
    # process the fa_pg_snap.dictSourceVols and then fetch the matching volume from fa_pg_snap.dictTargetVols
    # THIS IS DESTRUCTIVE!
    #
    my_result = fa_pg_snap.fMapVolumes( myArrayTgt, args.execute_lock )

    if my_result!="": fa_pg_snap.mQuit()


    #
    # if safety lock engaged there is nothing more we can do
    #
    if( args.execute_lock ): fa_pg_snap.mQuit()



    # do we have a target db
    # scsi rescan?
    # asm rescan / relist
    # asm mount the source asm dg

    if ( fa_pg_snap.dictArgs.get( "rescan_scsi_bus", not_defined ) != not_defined ):

        print( '============' )
        os.system( fa_pg_snap.dictArgs.get( "rescan_scsi_bus" ))


    #
    # bring the ASM diskgroups online
    #
    if( asm_sid != not_defined and asm_home != not_defined ):

        nFail=0

        print( '============'  )
        print( "mounting ASM diskgroups on target" )

        source_asm_dg = dictDBParams.get( "asm_disk_groups", "" )
        mMountASMDG( asm_sid, asm_home, source_asm_dg.split(',') )
        lstMountedDGs = fQueryASMDGMounted( asm_sid, asm_home, source_asm_dg.split(',') )

        for dg in source_asm_dg.split(','):
            if dg not in lstMountedDGs:
                print( f'ASM diskgroup {dg} has not mounted on target' )
                nFail+=1

        if( nFail>0 ): fa_pg_snap.mQuit( 'not all ASM diskgroups came online on the target' )

        print( 'all ASM diskgroups mounted on the target' )

    #
    # start the database
    # what is the required state?
    # down, started, mounted, open
    #

    print( '============'  )
    print( f'requested state of {ora_sid} is:{ora_target_mode.upper()}' )

    if( ora_target_mode.upper() != "DOWN" ):

        # reset the SPFILE to match the source
        mOraStartTarget( ora_sid, ora_home, "STARTED", (True if dictDBParams.get( 'backup_mode' )=="Yes" else False ) )
        mOraResetTargetSPFILE( ora_sid, ora_home )

        mOraStartTarget( ora_sid, ora_home, ora_target_mode.upper(), (True if dictDBParams.get( 'backup_mode' )=="Yes" else False ) )
        caTargetOraStatus = fQueryTargetInstanceRunning( ora_sid, ora_home )

        # if we are a container database....
        myres = dictDBParams.get( 'enable_pluggable_database', [] )
        if( myres=='TRUE' ):

            print( 'opening pluggable databases' )
            mOraStartPluggable( ora_sid, ora_home, ora_target_mode.upper() )

        print( f'actual state of {ora_sid} is:{caTargetOraStatus.upper()}' )


    #
    # end of program
    #
    print( '============' )
    print( 'complete' )


if __name__ == "__main__": doMain()



