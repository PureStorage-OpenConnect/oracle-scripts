#
# Python script to snapshot multiple Oracle databases and optionally re-sync to a target PG
# this version runs on a remote host using ssh access to the source and target
#
# Graham Thornton - Nov 2025
# gthornton@purestorage.com
#
# requires py_pure_client
# requires python -m pip install 'setuptools<72.0.0'
# requires python -m pip install oracledb
# requires fa_pg_snap
#
# usage:
# python fa_bulk_ora_snap.py -s gct-oradb-vvol-ac::pgroup-auto -t gct-oradb-vvol-pg-swingtarget -n gct1 -f config.json -x
#

import sys
import os
import re
import datetime
import time
import json
import argparse
import oracledb
import getpass
import paramiko

import warnings
warnings.filterwarnings(action='ignore')

from pypureclient import flasharray
import urllib3

#
# this script builds upon fa_pg_snap
#
import fa_pg_snap
import fa_pg_ora_snap

# global variables
halt=1
nohalt=0
version = "1.9.0"
not_defined = "Not Defined"

# disable the HTTPS warnings
urllib3.disable_warnings()

gnDebug=0

fa_pg_snap.dictArgs = {}


def mDebug( my_debug, my_msg ):
    if( gnDebug>=my_debug ): print( f'{my_msg}' )


#
# take a list and return it as a single string formatted as a CSV
#
def fList2CSV( my_list ):

    result=""
    sep=""

    for entry in my_list:
        result=result+sep+entry.strip()
        sep=","

    return result

##############################################

# REMOTE EXECUTION

##############################################

#
# execute the commands in the list my_commands against the remote host
#
def fRemoteExecuteOS( my_host, my_port, my_user, my_pass, my_commands ):

    lst_return=[]
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:

        ssh.connect( my_host, port=my_port, username=my_user, password=my_pass )

        for my_command in my_commands:

           # print( my_command )
            stdin, stdout, stderr=ssh.exec_command( my_command )
            stdin.write( my_pass+'\n' )
            stdin.flush( )

            for out in stdout.readlines(): lst_return.append( out )

        ssh.close()

        return lst_return

    except paramiko.AuthenticationException:
        print("Authentication failed, please check your username and password.")
        return lst_return
    except paramiko.SSHException as e:
        print(f"SSH connection error: {e}")
        return lst_return
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return lst_return

#
# copy the local file to the remote host
#
def mRemoteCopyFile( my_host, my_port, my_user, my_pass, my_local_file, my_remote_file ):

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:

        ssh.connect( my_host, port=my_port, username=my_user, password=my_pass )

        sftp_client = ssh.open_sftp()

        sftp_client.put( my_local_file, my_remote_file)
        mDebug( 3, "file "+my_local_file+" uploaded to "+my_remote_file+" successfully" )

        sftp_client.close()
        ssh.close()

    except paramiko.AuthenticationException:
        print("Authentication failed, please check your username and password.")
    except paramiko.SSHException as e:
        print(f"SSH connection error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


##############################################

# REMOTE SQL EXECUTION

##############################################


#
# execute the commands in the list my_commands against the remote host
#
def fRemoteExecuteSQL( my_host, my_port, my_user, my_pass, my_sid, my_cs, my_filter, my_sql_commands ):

    lst_return=[]
    result_set=[]

    # copy the SQL commands to the remote host
    lst_commands=[]
    lst_commands.append( "echo '"+my_cs+"' > /tmp/pure.sql" )
    lst_commands.append( "echo 'set linesize 255' >> /tmp/pure.sql" )
    lst_commands.append( "echo 'set pagesize 999' >> /tmp/pure.sql" )
    for my_sql_command in my_sql_commands:
        lst_commands.append( "echo '"+my_sql_command+"' >> /tmp/pure.sql" )
    lst_commands.append( "echo 'exit;' >> /tmp/pure.sql" )

    # execute the command to create the SQL script on the remote host
    lst_return=fRemoteExecuteOS( my_host, my_port, my_user, my_pass, lst_commands )

    # swap out curly braces for ticks in the file we copied
    lst_return=fRemoteExecuteOS( my_host, my_port, my_user, my_pass, ["sed -i \"s/{/\'/g; s/}/\'/g\" /tmp/pure.sql"] )

    # prepare to execute the SQL commands
    lst_commands=[]
    lst_commands.append( "export ORAENV_ASK=NO; export ORACLE_SID="+my_sid+"; . oraenv; sqlplus -s /nolog @/tmp/pure.sql" )
    #if( gnDebug==0 ): lst_commands.append( "rm /tmp/pure.sql" )

    # execute the command to create the SQL script on the remote host
    result_set=fRemoteExecuteOS( my_host, my_port, my_user, my_pass, lst_commands )

    # if filter then only return lines that start with RES:
    if len(my_filter)>0:
        for result in result_set:
            if result.startswith( my_filter ):
                result=result.strip()
                mDebug( 5, result )
                lst_return.append( result[len(my_filter):] )

    else:
        lst_return=result_set

    return lst_return

#
# remote execute a SQL script
# copy the script to the remote host and then execute it, deleting it after
#
def fRemoteExecuteSQLFile( my_host, my_port, my_user, my_pass, my_sid, my_cs, my_filter, my_local_file ):

    lst_return=[]

    if( os.path.isfile( my_local_file)):

        my_remote_file= '/tmp/'+os.path.basename(my_local_file)

        mRemoteCopyFile( my_host, my_port, my_user, my_pass, my_local_file, my_remote_file )

        lst_return = fRemoteExecuteSQL( my_host, my_port, my_user, my_pass, my_sid, my_cs, my_filter, ['@'+my_remote_file] )

        # clean up
        if( gnDebug==0 ): fRemoteExecuteOS( my_host, my_port, my_user, my_pass, ['rm '+my_remote_file] )

    else:
        print( f'error: file {my_local_file} does not exist or is not a file' )

    return lst_return


##############################################

# REMOTE DATABASE MANAGEMENT

##############################################

#
# startup the database on the remote node
#
def fASMMountRemote( my_host, my_port, my_user, my_pass, my_sid, my_asm_diskgroups ):

    lst_commands=["export ORAENV_ASK=NO; export ORACLE_SID="+my_sid+"; . oraenv; asmcmd mount "+my_asm_diskgroups]

    fRemoteExecuteOS( my_host, my_port, my_user, my_pass, lst_commands )


#
# start the target instance to the required state
#

def mOraStartTargetRemote( my_host, my_port, my_user, my_pass, my_sid, my_cs, ora_target_mode, ora_backup_mode ):

    if ora_target_mode=="DOWN": return

    cmd_list=["startup nomount;"]

    if ora_target_mode=="MOUNTED" or ora_target_mode=="OPEN":

        cmd_list.append( "alter database mount;" )

        if ora_backup_mode: cmd_list.append( "alter database end backup;" )

    if ora_target_mode=="OPEN": cmd_list.append( "alter database open;" )

    #print( cmd_list )

    myres =  fRemoteExecuteSQL( my_host, my_port, my_user, my_pass, my_sid, my_cs, "", cmd_list )


#
# reset the SPFILE of the target database
#
def mOraResetTargetSPFILERemote( my_host, my_port, my_user, my_pass, my_sid, my_cs ):

    print( 'resetting the target SPFILE' )

    cmd_list = []

    # reset the database name
    value = fa_pg_ora_snap.dictDBParams.get( 'db_name' )
    cmd = "alter system set db_name='"+value+"' sid='*' scope=spfile;"
    cmd_list.append( cmd )
    print( cmd )

    for parameter in fa_pg_ora_snap.lst_db_parameters:

        value = fa_pg_ora_snap.dictDBParams.get( parameter )

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
    cmd_list.append( 'shutdown immediate' );

    fRemoteExecuteSQL( my_host, my_port, my_user, my_pass, my_sid, my_cs, "", cmd_list )

#
# open pluggable databases
#

def mOraStartPluggableRemote( my_host, my_port, my_user, my_pass, my_sid, my_cs, ora_target_mode ):

    if ora_target_mode!="OPEN": return

    cmd_list = []

    open_pdbs = fa_pg_ora_snap.dictDBParams.get( 'open_pdbs', not_defined )

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

    fRemoteExecuteSQL( my_host, my_port, my_user, my_pass, my_sid, my_cs, "", cmd_list )



##############################################

# MAIN BLOCK

##############################################

def doMain( ):

    # parse the command line args
    parser = argparse.ArgumentParser(
                    prog='fa_pg_ora_snap_remote ', usage='%(prog)s [-s -t -n -f -i -r -b -o -x -h]',
                    description='snapshot a protection group of an oracle database on a Pure Flash Array',
                    epilog='coded by Graham Thornton - gthornton@purestorage.com')

    parser.add_argument('-s','--source_protection_group', help='source pg', required=False)
    parser.add_argument('-t','--target_protection_group', help='target pg', required=False)
    parser.add_argument('-n','--snapshot_name', help='name of the snapshot', required=True)
    parser.add_argument('-f','--config_file', help='json document of config options', required=True)
    parser.add_argument('-i','--ignore_match', action='store_true', help='ignore tag-matching')
    parser.add_argument('-r','--replicate', action='store_true', help='replicate snapshot')
    parser.add_argument('-b','--backup_mode', action='store_true', help='put source database into backup mode')
    parser.add_argument('-o','--open_mode', help='requested state of the target instance (down, started, mounted, open)', required=False)
    parser.add_argument('-x','--execute_lock', action='store_false', help="specify -x to actually snap the database (default is safety lock on)")

    args = parser.parse_args()


    print( '============' )
    print( f'fa_pg_ora_snap_remote.py {version} started at {datetime.datetime.now()}' )

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
        fa_pg_snap.mQuit( 'src_flash_array_host and xrc_flash_array_api_token need to be defined in the config file or environment variables' )


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
    caSourceProtectionGroup=fa_pg_snap.fNotNone( args.source_protection_group, fa_pg_snap.dictArgs.get ( "src_protection_group", not_defined ))
    caTargetProtectionGroup=fa_pg_snap.fNotNone( args.target_protection_group, fa_pg_snap.dictArgs.get ( "tgt_protection_group", not_defined ))

    #
    # check if the source pg has the requested snapshot
    #

    bSourceSnapshotExists=fa_pg_snap.fQuerySnapExists( myArraySrc, caSnapshotName, caSourceProtectionGroup )

    print( f'source protection group:{caSourceProtectionGroup}' )
    print( f'target protection group:{caTargetProtectionGroup}' )


    ora_target_mode = fa_pg_snap.fNotNone( args.open_mode, fa_pg_snap.dictArgs.get( "oracle_target_mode", "DOWN" ))
    ora_target_mode = ora_target_mode.upper()


    # check if we want oracle backup mode used
    bBackupMode = fa_pg_snap.fDictBool( "ora_backup_mode", False )
    bBackupMode = ( bBackupMode | bool(args.backup_mode) )


    # connect to the source, read v$parameter and put it into backup mode
    dbSourceConnection = fa_pg_ora_snap.fOraSourceConnect( bSourceSnapshotExists, bBackupMode )

    #
    # if the snapshot does not exist create it
    # if safety lock engaged this will return a null string
    #

    if( not bSourceSnapshotExists ): caSnapshotName=fa_pg_snap.fCreateSnapshot( myArraySrc, args.execute_lock, caSnapshotName, caSourceProtectionGroup, args.replicate, [] )


    #
    # come out of backup mode
    # if we have a source db connection, we made a snapshot and we wanted backup mode
    #

    if ( not bSourceSnapshotExists and dbSourceConnection != None and bBackupMode ):

        print( '============' )
        print( 'source db end backup mode' )
        fa_pg_ora_snap.mSQLExecute( dbSourceConnection, "alter database end backup" )



    #
    # query the volumes of the source pg
    # these are collected in lst_source_vols
    #
    lstSourceVols = fa_pg_snap.fQueryVolsinPG( myArraySrc, caSourceProtectionGroup )



    #
    # tag the snapshot volumes with all of the key values read from the source database
    #
    fa_pg_ora_snap.mTagSnapshot( myArraySrc, bSourceSnapshotExists, lstSourceVols, caSourceProtectionGroup, caSnapshotName, args.execute_lock, False )


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
    #if caTargetProtectionGroup==not_defined: fa_pg_snap.mQuit( )


    # collect the data to connect to the target host
    tgt_host        = fa_pg_snap.dictArgs.get( "tgt_host", "not_found" )
    tgt_port        = fa_pg_snap.dictArgs.get( "tgt_port",        fa_pg_snap.dictArgs.get( "def_port", 22 ))
    tgt_user_oracle = fa_pg_snap.dictArgs.get( "tgt_user_oracle", fa_pg_snap.dictArgs.get( "def_user_oracle", "oracle" ))
    tgt_pass_oracle = fa_pg_snap.dictArgs.get( "tgt_pass_oracle", fa_pg_snap.dictArgs.get( "def_pass_oracle", "oracle" ))
    tgt_user_grid   = fa_pg_snap.dictArgs.get( "tgt_user_grid",   fa_pg_snap.dictArgs.get( "def_user_grid", "grid" ))
    tgt_pass_grid   = fa_pg_snap.dictArgs.get( "tgt_pass_grid",   fa_pg_snap.dictArgs.get( "def_pass_oracle", "grid" ))
    tgt_db          = fa_pg_snap.dictArgs.get( "tgt_db" )
    tgt_sid         = fa_pg_snap.dictArgs.get( "tgt_sid", tgt_db )
    tgt_cs_db       = fa_pg_snap.dictArgs.get( "tgt_cs_db",       fa_pg_snap.dictArgs.get( "def_cs_db", "connect / as sysdba" ))
    tgt_asm         = fa_pg_snap.dictArgs.get( "tgt_asm",         fa_pg_snap.dictArgs.get( "def_asm", "+ASM" ))
    tgt_cs_asm      = fa_pg_snap.dictArgs.get( "tgt_cs_asm",      fa_pg_snap.dictArgs.get( "def_cs_asm", "connect / as sysasm" ))


    #
    # check target database is down
    #
    print( '============' )
    print( f'checking target instance {tgt_sid} on host {tgt_host} is down' )
    sql_result = fRemoteExecuteSQL( tgt_host, tgt_port, tgt_user_oracle, tgt_pass_oracle, tgt_sid, tgt_cs_db, "RES:", ["select {RES:}||name from v$database;"] )
    result = ', '.join(sql_result)
    if( len( result )>0 ):
        fa_pg_snap.mError( halt, 0, 'target database appears to be still be online:'+result )

    #
    # check asm diskgroups are unmounted
    #
    print( '============' )
    src_asm_diskgroups = fa_pg_ora_snap.dictDBParams.get( "asm_disk_groups" )
    print( f'checking target ASM diskgroups are unmounted: {src_asm_diskgroups}' )

    lst_src_asm_diskgroups = src_asm_diskgroups.split(',')
    mounted=0

    lst_tgt_asm_diskgroups = fRemoteExecuteSQL( tgt_host, tgt_port, tgt_user_grid, tgt_pass_grid, tgt_asm, tgt_cs_asm, "RES:", ["select {RES:}||name from v$asm_diskgroup where state = {MOUNTED};"] )
    for tgt_diskgroup in lst_tgt_asm_diskgroups:
        if ( tgt_diskgroup.strip() in lst_src_asm_diskgroups ):
            mounted+=1
            fa_pg_snap.mError( nohalt, 0, 'target ASM diskgroup '+tgt_diskgroup.strip()+' is still mounted' )

    if( mounted>0 ): fa_pg_snap.mError( halt, 0, 'target ASM diskgroups still mounted' ) 



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


    # rescan scsi bus of remote target
    print( '============' )
    print( f'rescaning the SCSI bus on target {tgt_host}' )
    rescan_scsi_bus = fa_pg_snap.dictArgs.get( "rescan_scsi_bus", not_defined )

    if( rescan_scsi_bus != not_defined):

        lst_return=fRemoteExecuteOS( tgt_host, tgt_port, tgt_user_grid, tgt_pass_grid, [rescan_scsi_bus] )
        #print( lst_return )

    else: 
        print( 'SCSI bus rescan command not defined' )

    # mount ASM diskgorups on remote target
    print( '============' )
    print( f'mounting ASM diskgroups on target {tgt_host}' )
    fASMMountRemote( tgt_host, tgt_port, tgt_user_grid, tgt_pass_grid, tgt_asm, src_asm_diskgroups )

    #
    # check asm diskgroups are mounted
    #
    print( '============' )
    print( f'checking target ASM diskgroups are mounted: {src_asm_diskgroups}' )

    mounted=0

    lst_tgt_asm_diskgroups = fRemoteExecuteSQL( tgt_host, tgt_port, tgt_user_grid, tgt_pass_grid, tgt_asm, tgt_cs_asm, "RES:", ["select {RES:}||name from v$asm_diskgroup where state = {MOUNTED};"] )
    for src_diskgroup in lst_src_asm_diskgroups:
        if ( src_diskgroup not in lst_tgt_asm_diskgroups ):
            mounted+=1
            fa_pg_snap.mError( nohalt, 0, 'source ASM diskgroup '+src_diskgroup.strip()+' failed to mount' )
        else:
            print( f'ASM diskgroup {src_diskgroup} mounted on target' )

    if( mounted>0 ): fa_pg_snap.mError( halt, 0, 'not all ASM diskgroups mounted on target' )



    #
    # start the database
    # what is the required state?
    # down, started, mounted, open
    #

    print( '============'  )
    print( f'requested state of {tgt_sid} is:{ora_target_mode.upper()}' )

    if( ora_target_mode.upper() != "DOWN" ):

        # reset the SPFILE to match the source
        mOraStartTargetRemote( tgt_host, tgt_port, tgt_user_oracle, tgt_pass_oracle, tgt_sid, tgt_cs_db, "STARTED", False )

        # reset the target SPFILE
        mOraResetTargetSPFILERemote( tgt_host, tgt_port, tgt_user_oracle, tgt_pass_oracle, tgt_sid, tgt_cs_db )

        # restart the instance 
        print( f'restarting instance' )
        mOraStartTargetRemote( tgt_host, tgt_port, tgt_user_oracle, tgt_pass_oracle, tgt_sid, tgt_cs_db, ora_target_mode, (True if fa_pg_ora_snap.dictDBParams.get( 'backup_mode' )=="Yes" else False ) )

        # check state of the target database
        sql_result = fRemoteExecuteSQL( tgt_host, tgt_port, tgt_user_oracle, tgt_pass_oracle, tgt_sid, tgt_cs_db, "RES:", ["select {RES:}||status from v$instance;"] )
        caTargetOraStatus = ', '.join(sql_result)

        # if we are a container database....
        myres = fa_pg_ora_snap.dictDBParams.get( 'enable_pluggable_database', [] )
        if( myres=='TRUE' ):

            print( 'opening pluggable databases' )
            mOraStartPluggableRemote( ora_sid, ora_home, ora_target_mode.upper() )

        print( f'actual state of {tgt_sid} on host {tgt_host} is:{caTargetOraStatus.upper()}' )




    #
    # end of program
    #
    print( '============' )
    print( 'complete' )


if __name__ == "__main__": doMain()

