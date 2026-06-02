#
# Python script to snapshot multiple Oracle databases and optionally re-sync to a target PG
# this version runs on a remote host using ssh access to the source and target
#
# Graham Thornton - Jun 2026
# gthornton@everpuredata.com
#
# from_private_key function copied from web - author unknown
#
# requires py_pure_client
# requires python -m pip install 'setuptools<72.0.0'
# requires python -m pip install oracledb
# requires fa_pg_snap
# requires fa_pg_ora_snap
#
# usage:
# python fa_pg_ora_snap.rac.py -s gct-oradb-vvol-ac::pgroup-auto -t gct-oradb-vvol-pg-swingtarget -n gct1 -f config.json -x
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

# added for from_private_key function
from io import StringIO
from paramiko import RSAKey, Ed25519Key, ECDSAKey, DSSKey, PKey
from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, dsa, rsa, ec

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

def from_private_key(file_name, password=None) -> PKey:

    # open the key file
    #file_obj = open(file_name, "r", encoding="utf-8") as file:
    file_obj = open(file_name, "r", encoding="utf-8")

    private_key = None
    file_bytes = bytes(file_obj.read(), "utf-8")
    try:
        key = crypto_serialization.load_ssh_private_key(
            file_bytes,
            password=password,
        )
        file_obj.seek(0)
    except ValueError:
        key = crypto_serialization.load_pem_private_key(
            file_bytes,
            password=password,
        )
        if password:
            encryption_algorithm = crypto_serialization.BestAvailableEncryption(
                password
            )
        else:
            encryption_algorithm = crypto_serialization.NoEncryption()
        file_obj = StringIO(
            key.private_bytes(
                crypto_serialization.Encoding.PEM,
                crypto_serialization.PrivateFormat.OpenSSH,
                encryption_algorithm,
            ).decode("utf-8")
        )
    if isinstance(key, rsa.RSAPrivateKey):
        private_key = RSAKey.from_private_key(file_obj, password)
    elif isinstance(key, ed25519.Ed25519PrivateKey):
        private_key = Ed25519Key.from_private_key(file_obj, password)
    elif isinstance(key, ec.EllipticCurvePrivateKey):
        private_key = ECDSAKey.from_private_key(file_obj, password)
    elif isinstance(key, dsa.DSAPrivateKey):
        private_key = DSSKey.from_private_key(file_obj, password)
    else:
        raise TypeError
    return private_key

#
# establishes a remote shell
# passes back a handle to the channel
# used to start SQL sessions and pass commands
#
def fRemoteOSShell( my_host, my_port, my_user, my_pass, my_key ):

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        if( my_key != not_defined ):

            #ssh_key=paramiko.RSAKey.from_private_key_file( my_key )
            mDebug( 3, f'key file:{my_key}' )
            ssh_key=from_private_key( my_key )
            ssh.connect( my_host, port=my_port, username=my_user, pkey=ssh_key )

        else:

            ssh.connect( my_host, port=my_port, username=my_user, password=my_pass )

        shell = ssh.invoke_shell()

        time.sleep(0.5)

        return shell

    except:

        return null

#
# execute the commands in the list my_commands against the remote host
# returns a list of the output gathered
#
def fRemoteOSExecute( my_host, my_port, my_user, my_pass, my_key, my_commands ):

    lst_return=[]
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:

        if( my_key != not_defined ):

            #ssh_key=paramiko.RSAKey.from_private_key_file( my_key )
            mDebug( 3, f'key file:{my_key}' )
            ssh_key=from_private_key( my_key )
            ssh.connect( my_host, port=my_port, username=my_user, pkey=ssh_key )

        else:

            ssh.connect( my_host, port=my_port, username=my_user, password=my_pass )

        for my_command in my_commands:

           # print( my_command )
            stdin, stdout, stderr=ssh.exec_command( my_command )
            stdin.write( my_pass+'\n' )
            stdin.flush( )

            for out in stdout.readlines(): lst_return.append( out.strip() )

        ssh.close()

        mDebug( 3, f'fRemoteOSExecute: {lst_return}' )

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
# pass commands to the already established remote shell
# filter the responses is my_filter is not null
# return results as a string
#
def fRemoteOSExecuteShell( my_shell, my_commands, my_filter="", my_wait=0.5 ):

    #get_join = lambda my_string: "" if len(my_string)==0 else "\n"

    # clear anything already in the return buffer
    while my_shell.recv_ready(): my_shell.recv(65535).decode()

    lst_return=[]
    #my_output = ""

    try:

        for my_command in my_commands:

            # execute the command
            my_shell.send(my_command + "\n")
            time.sleep(my_wait)

            # process the result
            while my_shell.recv_ready():
                myout=my_shell.recv(65535).decode()
                lst_out = myout.splitlines()

                for out in lst_out:

                    match=False
                    if len(my_filter)==0: match = True
                    if len(my_filter)>0: match = re.search(my_filter,out)

                    if match:
                        #print( f'out:*{out}* {len(out)}' )
                        #my_output += get_join(my_output)+out.strip()
                        lst_return.append( out.strip() )

    except:
        return ["fRemoteOSExecuteShell failed"]

    #return my_output
    return lst_return


#
# copy the local file to the remote host
#
def mRemoteCopyFile( my_host, my_port, my_user, my_pass, my_key, my_local_file, my_remote_file ):

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:

        if( my_key != not_defined ):

            ssh.connect( my_host, port=my_port, username=my_user, password=my_pass )

        else:

            #ssh_key=paramiko.RSAKey.from_private_key_file( my_key )
            ssh_key=from_private_key( my_key )
            ssh.connect( my_host, port=my_port, username=my_user, pkey=ssh_key )

        sftp_client = ssh.open_sftp()

        sftp_client.put( my_local_file, my_remote_file )
        mDebug( 3, f'file {my_local_file} uploaded to {my_remote_file} successfully' )

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
def fRemoteSQLExecute( my_host, my_port, my_user, my_pass, my_key, my_sid, my_cs, my_filter, my_sql_commands ):

    result_set=[]

    # prepare to execute the SQL commands
    lst_commands=[]
    lst_commands.append( "export ORAENV_ASK=NO" )
    lst_commands.append( "export ORACLE_SID="+my_sid )
    lst_commands.append( ". oraenv" )
    lst_commands.append( "sqlplus -s /nolog" )
    lst_commands.append( "set linesize 255" )
    lst_commands.append( "set pagesize 999" )
    lst_commands.append( my_cs )
    lst_commands += my_sql_commands

    lst_commands.append( "exit;" )

    # open a shell on the remote host
    my_shell=fRemoteOSShell( my_host, my_port, my_user, my_pass, my_key )

    # now execute the commands
    result_set=fRemoteOSExecuteShell( my_shell, lst_commands, my_filter, 0.5 )

    mDebug( 2, f'fRemoteSQLExecute: {result_set}' )

    my_shell.close()

    return result_set

#
# remote execute a SQL script
# copy the script to the remote host and then execute it, deleting it after
#
def fRemoteSQLExecuteFile( my_host, my_port, my_user, my_pass, my_key, my_sid, my_cs, my_filter, my_local_file ):

    lst_return=[]

    if( os.path.isfile( my_local_file)):

        my_remote_file= '/tmp/'+os.path.basename(my_local_file)

        mRemoteCopyFile( my_host, my_port, my_user, my_pass, my_key, my_local_file, my_remote_file )

        lst_return = fRemoteSQLExecute( my_host, my_port, my_user, my_pass, my_key, my_sid, my_cs, my_filter, ['@'+my_remote_file] )

        # clean up
        if( gnDebug==0 ): fRemoteOSExecute( my_host, my_port, my_user, my_pass, my_key, ['rm '+my_remote_file] )

    else:
        print( f'error: file {my_local_file} does not exist or is not a file' )

    return lst_return


##############################################

# REMOTE DATABASE MANAGEMENT

##############################################

#
# startup the database on the remote node
#
def fASMMountRemote( my_host, my_port, my_user, my_pass, my_key, my_sid, my_asm_diskgroups ):

    lst_commands=["export ORAENV_ASK=NO; export ORACLE_SID="+my_sid+"; . oraenv; asmcmd mount "+my_asm_diskgroups]

    fRemoteOSExecute( my_host, my_port, my_user, my_pass, my_key, lst_commands )


#
# for a given host determine the ASM instance
#
def fQueryASMInstance( my_host, my_port, my_user, my_pass, my_key ):

    asm_instance=not_defined

    mDebug( 1, f'fQueryASMInstance host:{my_host} user:{my_user} pass:{my_pass}' )

    # is Oracle ASM installed?
    lst_commands=["ps -ef | grep -E '[a]sm_pmon_' | awk -F'_' '{print $NF}'"]
    lst_return=fRemoteOSExecute( my_host, my_port, my_user, my_pass, my_key, lst_commands )

    # check if we found an asm instance
    if lst_return:

        # record the asm instance on this host
        asm_instance=lst_return[0]

    return asm_instance

#
# for a given host and database name, determine the SID name
#
def fQueryDBInstance( my_host, my_port, my_user, my_pass, my_key, my_db, my_asm ):

    # which database instance is on this host?
    db_instance = not_defined

    lst_commands=["export ORAENV_ASK=NO; export ORACLE_SID="+my_asm+"; . oraenv; srvctl status database -database "+my_db+" | grep `hostname -s` | awk -F' ' '{print \"instance:\" $2 \":host:\" $NF}'" ]
    lst_return=fRemoteOSExecute( my_host, my_port, my_user, my_pass, my_key, lst_commands )

    # if succesful we will get back "instance:instance_name:host:host_name"
    # so lets walk the result list and look for the instance listed against this host
    for my_result in lst_return:

        lst_my_instance_and_host = my_result.split(':')

        # lines we are interested in will break into 4 pieces
        if( len( lst_my_instance_and_host )==4 ):

            if ( lst_my_instance_and_host[0]=="instance" and lst_my_instance_and_host[2]=="host" ):

                if ( lst_my_instance_and_host[3].strip() in my_host ): db_instance=lst_my_instance_and_host[1]

    # catch a no instance condition - probably single instance
    if( db_instance == not_defined ):

        lst_commands=["export ORAENV_ASK=NO; export ORACLE_SID="+my_asm+"; . oraenv; srvctl config database -db "+my_db+" | grep 'Database instance' | awk -F' ' '{print \"instance:\" $NF}'"]
        lst_return=fRemoteOSExecute( my_host, my_port, my_user, my_pass, my_key, lst_commands )

        for my_result in lst_return:

            lst_my_instance_and_host = my_result.split(':')

            # lines we are interested in will break into 2 pieces
            if( len( lst_my_instance_and_host )==2 ):

                if ( lst_my_instance_and_host[0]=="instance" ): db_instance = lst_my_instance_and_host[1].strip()

    return db_instance

#
# start the target database to the required state
#

def mOraStartTargetRemote ( my_host, my_port, my_user, my_pass, my_key, my_db, my_cs, ora_target_mode, ora_backup_mode ):

    db_instance=not_defined
    open_hot_backup=False

    if ora_target_mode=="DOWN": return not_defined

    # check the requested state is valid
    if ( ora_target_mode not in ['OPEN','MOUNT','NOMOUNT'] ):
        print( f'target database state must be one of OPEN, MOUNT, NOMOUNT, DOWN' )
        return not_defined

    sql_cmd_list=[];

    # which ASM instance is on this host?
    asm_instance = fQueryASMInstance( my_host, my_port, my_user, my_pass, my_key )
    if( asm_instance==not_defined): fa_pg_snap.mQuit( 'ASM instance not found on host '+my_host )

    # which database instance is on this host?
    db_instance = fQueryDBInstance( my_host, my_port, my_user, my_pass, my_key, my_db, asm_instance )
    if( db_instance==not_defined): fa_pg_snap.mQuit( 'database instance for '+my_db+' not found on host '+my_host )

    #print( f'asm:{asm_instance} db:{db_instance}' )
    print( f'starting database {my_db} to a {ora_target_mode} state using host {my_host} and database instance {db_instance}' )

    # if we are in backup mode, and want to move to open
    # we will need to disable that before opening the database
    if ora_backup_mode and ora_target_mode =='OPEN':
        ora_target_mode = 'MOUNT'
        open_hot_backup = True

    # start the database (on all nodes)
    lst_commands=["export ORAENV_ASK=NO; export ORACLE_SID="+db_instance+"; . oraenv; srvctl start database -d "+my_db+" -o "+ora_target_mode]
    fRemoteOSExecute( my_host, my_port, my_user, my_pass, my_key, lst_commands )

    # if no mount requested we stop here
    if ora_target_mode=="NOMOUNT": return db_instance

    # we are in backup mode - so come out of that - we may also need to open the database
    if ora_backup_mode:

        print( f'taking target database out of backup mode using instance {db_instance}' )
        #print( f'host:{my_host} user:{my_user} pass:{my_pass} cs:{my_cs}' )

        result = fRemoteSQLExecute( my_host, my_port, my_user, my_pass, my_key, db_instance, my_cs, "", ["alter database end backup;"] )
        mDebug( 2, f'mOraStartTargetRemote: {result}' )

    if ora_backup_mode and open_hot_backup:

        print( f'restarting target database with backup mode disabled' )

        lst_commands=["export ORAENV_ASK=NO; export ORACLE_SID="+db_instance+"; . oraenv; srvctl stop database -d "+my_db+" -o immediate"]
        fRemoteOSExecute( my_host, my_port, my_user, my_pass, my_key, lst_commands )

        lst_commands=["export ORAENV_ASK=NO; export ORACLE_SID="+db_instance+"; . oraenv; srvctl start database -d "+my_db]
        fRemoteOSExecute( my_host, my_port, my_user, my_pass, my_key, lst_commands )


    # return the database instance we found on this host
    return db_instance

#
# shut the database down
# used to stop the target database (all instances) so that the spfile is re-read
#

def mOraStopTargetRemote ( my_host, my_port, my_user, my_pass, my_key, my_db ):

    db_instance=not_defined

    # which ASM instance is on this host?
    asm_instance = fQueryASMInstance( my_host, my_port, my_user, my_pass, my_key )

    # which database instance is on this host?
    db_instance = fQueryDBInstance( my_host, my_port, my_user, my_pass, my_key, my_db, asm_instance )

    print( f'shutting down database {my_db} using host {my_host} and database instance {db_instance}' )

    # stop the database (on all nodes)
    lst_commands=["export ORAENV_ASK=NO; export ORACLE_SID="+asm_instance+"; . oraenv; srvctl stop database -d "+my_db+" -o immediate"]
    fRemoteOSExecute( my_host, my_port, my_user, my_pass, my_key, lst_commands )

    # return the database instance we found on this host
    return db_instance

#
# reset the SPFILE of the target database
#
def mOraResetTargetSPFILERemote( my_host, my_port, my_user, my_pass, my_key, my_sid, my_cs ):

    print( f'resetting the target SPFILE on host {my_host} using instance {my_sid}' )

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

    # execute all the SPFILE changes
    myresult = fRemoteSQLExecute( my_host, my_port, my_user, my_pass, my_key, my_sid, my_cs, "", cmd_list )
    mDebug( 4, f'mOraResetTargetSPFILERemote {myresult}' )


#
# open pluggable databases
#

def mOraStartPluggableRemote( my_host, my_port, my_user, my_pass, my_key, my_sid, my_cs, ora_target_mode ):

    if ora_target_mode!="OPEN": return

    cmd_list = []

    open_pdbs = fa_pg_ora_snap.dictDBParams.get( 'open_pdbs', not_defined )

    local_listener  = fa_pg_snap.dictArgs.get( 'local_listener', not_defined )

    if( open_pdbs == not_defined ):
        print( 'no pluggable databases to re-open' )
        return

    for open_pdb in open_pdbs.split(','):

        print( 'opening '+str(open_pdb))
        cmd_list.append( "alter pluggable database "+str(open_pdb)+" open;" )
        cmd_list.append( "alter session set container="+str(open_pdb)+";" )
        if ( local_listener != not_defined ):
            cmd_list.append( "alter system set local_listener='"+local_listener+"';" )
            cmd_list.append( "alter system register;" )
        cmd_list.append( "connect / as sysdba" )

        #print( str(cmd_list))

    fRemoteSQLExecute( my_host, my_port, my_user, my_pass, my_key, my_sid, my_cs, "", cmd_list )



##############################################

# MAIN BLOCK

##############################################

def doMain( ):

    # parse the command line args
    parser = argparse.ArgumentParser(
                    prog='fa_pg_ora_snap.rac ', usage='%(prog)s [-s -t -n -f -i -r -b -o -x -h]',
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
    print( f'fa_pg_ora_snap.rac.py {version} started at {datetime.datetime.now()}' )

    caSnapshotName=args.snapshot_name
    bSourceSnapshotExists=False

    #
    # read the config file
    #
    if( args.config_file != None ): fa_pg_snap.dictArgs = fa_pg_snap.fReadConnectionJSON( args.config_file )

    # fa variables for source array
    src_flash_array = fa_pg_snap.dictArgs.get( "src_flash_array_host", fa_pg_snap.dictArgs.get( "flash_array_host", os.environ.get('FA_HOST')))
    src_flash_array_api_token = fa_pg_snap.dictArgs.get( "src_flash_array_api_token", fa_pg_snap.dictArgs.get( "flash_array_api_token", os.environ.get('API_TOKEN')))
    flash_array_api_version = fa_pg_snap.dictArgs.get( "flash_array_api_version" )

    if( src_flash_array==None or src_flash_array_api_token==None ):
        fa_pg_snap.mQuit( 'src_flash_array_host and src_flash_array_api_token need to be defined in the config file or environment variables' )

    #
    # connect to the source FA
    #
    myArraySrc = fa_pg_snap.fFAConnect( src_flash_array, src_flash_array_api_token, flash_array_api_version )
    src_array_name = fa_pg_snap.fFAQueryName( myArraySrc )



    #
    # get the source and optional target protection groups
    #
        #
    # get the source and optional target protection groups
    #
    caSourceProtectionGroup=fa_pg_snap.fNotNone( args.source_protection_group, fa_pg_snap.dictArgs.get( "source_protection_group", fa_pg_snap.dictArgs.get( "src_protection_group", not_defined )))
    caTargetProtectionGroup=fa_pg_snap.fNotNone( args.target_protection_group, fa_pg_snap.dictArgs.get( "target_protection_group", fa_pg_snap.dictArgs.get( "tgt_protection_group", not_defined )))
    if( caSourceProtectionGroup==not_defined ): fa_pg_snap.mQuit( 'source protection group is not defined' )

    #
    # check if we want the snapshot to replicate
    #
    bReplicate = ( args.replicate or fa_pg_snap.dictArgs.get( "replicate" )=="True" )

    #
    # do we want to replicate this snapshot?
    #
    if( bReplicate ):

        # fa variables for target array
        tgt_flash_array = fa_pg_snap.dictArgs.get( "tgt_flash_array_host", os.environ.get('FA_HOST_TGT') )
        tgt_flash_array_api_token = fa_pg_snap.dictArgs.get( "tgt_flash_array_api_token", os.environ.get('API_TOKEN_TGT') )

        if( tgt_flash_array==None or tgt_flash_array_api_token==None ):
            fa_pg_snap.mQuit( 'tgt_flash_array_host and tgt_flash_array_api_token need to be defined in the config file or environment variables' )

        #
        # connect to the target FA
        #
        myArrayTgt = fa_pg_snap.fFAConnect( tgt_flash_array, tgt_flash_array_api_token, flash_array_api_version )
        tgt_array_name = fa_pg_snap.fFAQueryName( myArrayTgt )

    else:

        myArrayTgt = myArraySrc
        tgt_array_name = src_array_name


    #
    # check if the source pg has the requested snapshot
    #

    bSourceSnapshotExists=fa_pg_snap.fQuerySnapExists( myArraySrc, caSnapshotName, caSourceProtectionGroup )

    print( f'source protection group:{caSourceProtectionGroup}' )
    print( f'target protection group:{caTargetProtectionGroup}' )


    ora_target_mode = fa_pg_snap.fNotNone( args.open_mode, fa_pg_snap.dictArgs.get( "oracle_target_mode", "DOWN" ))
    ora_target_mode = ora_target_mode.upper()


    #
    # check if we want oracle backup mode used
    #
    bBackupMode = ( args.backup_mode or fa_pg_snap.dictArgs.get( "ora_backup_mode" )=="True" )


    # connect to the source, read v$parameter and put it into backup mode
    dbSourceConnection = fa_pg_ora_snap.fOraSourceConnect( bSourceSnapshotExists, bBackupMode )

    #
    # if the snapshot does not exist create it
    # if safety lock engaged this will return a null string
    #

    if( not bSourceSnapshotExists ): caSnapshotName=fa_pg_snap.fCreateSnapshot( myArraySrc, args.execute_lock, caSnapshotName, caSourceProtectionGroup, bReplicate, [] )


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
    lstSourceVols = fa_pg_snap.fQueryVolsinPG( myArraySrc, caSourceProtectionGroup, src_array_name )



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
    if caTargetProtectionGroup==not_defined: fa_pg_snap.mQuit( )


    # collect the data to connect to the target host
    lst_tgt_hosts   = fa_pg_snap.dictArgs.get( "tgt_hosts", [] )
    tgt_port        = fa_pg_snap.dictArgs.get( "tgt_port",        fa_pg_snap.dictArgs.get( "def_port", 22 ))

    tgt_user_oracle = fa_pg_snap.dictArgs.get( "tgt_user_oracle", fa_pg_snap.dictArgs.get( "def_user_oracle", "oracle" ))
    tgt_pass_oracle = fa_pg_snap.dictArgs.get( "tgt_pass_oracle", fa_pg_snap.dictArgs.get( "def_pass_oracle", not_defined ))
    tgt_key_oracle  = fa_pg_snap.dictArgs.get( "tgt_key_oracle",  not_defined )

    tgt_user_grid   = fa_pg_snap.dictArgs.get( "tgt_user_grid",   fa_pg_snap.dictArgs.get( "def_user_grid", tgt_user_oracle ))
    tgt_pass_grid   = fa_pg_snap.dictArgs.get( "tgt_pass_grid",   fa_pg_snap.dictArgs.get( "def_pass_grid", tgt_pass_oracle ))
    tgt_key_grid    = fa_pg_snap.dictArgs.get( "tgt_key_grid",    not_defined )

    tgt_db          = fa_pg_snap.dictArgs.get( "tgt_db" )
    tgt_cs_db       = fa_pg_snap.dictArgs.get( "tgt_cs_db",       fa_pg_snap.dictArgs.get( "def_cs_db", "connect / as sysdba" ))
    tgt_asm         = fa_pg_snap.dictArgs.get( "tgt_asm",         fa_pg_snap.dictArgs.get( "def_asm", "+ASM" ))
    tgt_cs_asm      = fa_pg_snap.dictArgs.get( "tgt_cs_asm",      fa_pg_snap.dictArgs.get( "def_cs_asm", "connect / as sysasm" ))


    #
    # is the target database configured on the target host
    #

    #
    # check target database and instances are down, and that the target ASM diskgroups are unmounted
    #
    lst_tgt_hosts = fa_pg_snap.dictArgs.get( "tgt_hosts", [] )

    # sanity check - do I have passwords and/or keys to connect?
    if( len( lst_tgt_hosts )>0 ):

        msg_credentials=""

        # if no grid key and grid=oracle, use the oracle key
        if( tgt_key_grid == not_defined and tgt_user_grid == tgt_user_oracle ): tgt_key_grid=tgt_key_oracle

        # we have no credentials for grid
        if( tgt_key_grid == not_defined and tgt_pass_grid == not_defined ): msg_credentials="no password or key provided for grid user"

        # we have no credentials for oracle
        if( tgt_key_grid == not_defined and tgt_pass_grid == not_defined ): msg_credentials+=(", " if len(msg_credentials)>0 else "" )+"no password or key provided for oracle user"

        print( '============' )
        if( msg_credentials != "" ): fa_pg_snap.mQuit( msg_credentials )
        if( tgt_key_grid != not_defined and tgt_user_grid != tgt_user_oracle ): print( f'will use ssh key to connect as grid' )
        if( tgt_key_grid == not_defined and tgt_user_grid != tgt_user_oracle ): print( f'will use password to connect as grid' )
        if( tgt_key_oracle != not_defined ): print( f'will use ssh key to connect as oracle' )
        if( tgt_key_oracle == not_defined ): print( f'will use password to connect as oracle' )


    for tgt_host_next in lst_tgt_hosts:

        print( '============' )

        # get the next target rac host
        tgt_host = tgt_host_next["tgt_host"]
        print( f'determining ASM instance on host {tgt_host}' )

        # is Oracle ASM installed?
        asm_instance = fQueryASMInstance( tgt_host, tgt_port, tgt_user_grid, tgt_pass_grid, tgt_key_grid )
        if ( asm_instance == not_defined ): fa_pg_snap.mError( halt, 0, 'ASM not installed or running on host '+tgt_host )
        print( f'ASM instance on this host is {asm_instance}' )

        # is the target database is configured
        print( f'checking if target database {tgt_db} is configured on host {tgt_host}' )

        my_status = 'target database is not configured'
        lst_commands=[]
        lst_commands.append( "export ORAENV_ASK=NO; export ORACLE_SID="+asm_instance+"; . oraenv; srvctl config | grep "+tgt_db )
        lst_return=fRemoteOSExecute( tgt_host, tgt_port, tgt_user_grid, tgt_pass_grid, tgt_key_grid, lst_commands )

        for myreturn in lst_return:
            if( tgt_db == myreturn.strip() ): my_status = 'target database is configured'

        # the specified node does not know of the target database
        if( my_status == 'target database is not configured' ): fa_pg_snap.mError( halt, 0, my_status+' on host '+tgt_host )

        # is the target database is configured
        print( f'checking if target database {tgt_db} is running on any host' )

        # is the target database running on any node?
        my_status = 'no instances of the database are running'
        lst_commands=[]
        lst_commands.append( "export ORAENV_ASK=NO; export ORACLE_SID="+asm_instance+"; . oraenv; srvctl status database -database "+tgt_db )
        lst_return=fRemoteOSExecute( tgt_host, tgt_port, tgt_user_grid, tgt_pass_grid, tgt_key_grid, lst_commands )

        # did Oracle say any instances of this database are running?
        for myreturn in lst_return:
            if ( "is running on node" in myreturn.strip()):
                my_status = 'database '+tgt_db+' is still running'
                print( f'{myreturn.strip()}' )

        # the target database is still running
        if( my_status != 'no instances of the database are running' ): fa_pg_snap.mError( halt, 0, my_status )


        #
        # check if target asm diskgroups are unmounted
        #
        print( '============' )
        src_asm_diskgroups = fa_pg_ora_snap.dictDBParams.get( "asm_disk_groups" )
        lst_src_asm_diskgroups = src_asm_diskgroups.split(',')
        mounted=0
        print( f'checking target ASM diskgroups are unmounted {src_asm_diskgroups} on host {tgt_host}' )

        lst_commands=[]
        lst_commands.append( "export ORAENV_ASK=NO; export ORACLE_SID="+asm_instance+"; . oraenv; asmcmd lsdg --suppressheader -g | grep 'MOUNTED' | awk -F' ' '{print $NF\",is mounted on node,\"$1}'" )
        lst_return=fRemoteOSExecute( tgt_host, tgt_port, tgt_user_grid, tgt_pass_grid, tgt_key_grid, lst_commands )

        # did we get any mounted diskgroups?
        for myreturn in lst_return:

            if ( "is mounted on node" in myreturn.strip()):

                #print( f'{myreturn.strip()}' )

                # each mounted diskgroup is a DG,NODE tuple
                myasmdg=myreturn.split(',')[0]
                myasmdg=myasmdg.rstrip("/")

                mynode=myreturn.split(',')[2]
                mynode=mynode.strip()

                # an ASM diskgroup used by the source database is mounted on one of the target nodes
                if( myasmdg in lst_src_asm_diskgroups ):
                    print( f'target ASM diskgroup {myasmdg} is still mounted on node {mynode}' )
                    mounted+=1

    # if we have target hosts, the mounted variable should be zero
    if( len( lst_tgt_hosts )>0 and mounted>0 ): fa_pg_snap.mError( halt, 0, 'target ASM diskgroups still mounted' )



    #
    # query the volumes of the target pg
    # collect these in lstTargetVols
    #
    lstTargetVols = fa_pg_snap.fQueryVolsinPG( myArrayTgt, caTargetProtectionGroup, tgt_array_name )


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
    if( bReplicate and not bSourceSnapshotExists ):

        retval = fa_pg_snap.fQuerySnapshotReplication( myArrayTgt, src_array_name, caSourceProtectionGroup, caSnapshotName, 10, 5, args.execute_lock )
        if( retval==False ):
            mError( halt, 0, 'snapshot replication did not complete in the time allowed' )

        fa_pg_ora_snap.mTagSnapshot( myArrayTgt, bSourceSnapshotExists, lstSourceVols, caSourceProtectionGroup, caSnapshotName, args.execute_lock, True )


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

    print( '============' )

    #
    # if there are no target hosts to mount to, we are done
    #
    if( len( lst_tgt_hosts )== 0 ):

        print( 'no target hosts defined' )
        fa_pg_snap.mQuit()


    # rescan scsi bus of remote targets
    rescan_scsi_bus = fa_pg_snap.dictArgs.get( "rescan_scsi_bus", not_defined )
    if( rescan_scsi_bus != not_defined):

        for tgt_host_next in lst_tgt_hosts:

            # get the next target rac host
            tgt_host = tgt_host_next["tgt_host"]

            print( f'rescaning the SCSI bus on target {tgt_host}' )

            lst_return=fRemoteOSExecute( tgt_host, tgt_port, tgt_user_grid, tgt_pass_grid, tgt_key_grid, [rescan_scsi_bus] )
            #print( lst_return )

    else:
        print( 'SCSI bus rescan command not defined' )



    # mount the ASM diskgroups on the target hosts
    print( '============' )
    for tgt_host_next in lst_tgt_hosts:

        # get the next target rac host
        tgt_host = tgt_host_next["tgt_host"]

        # query the asm instance for this host
        asm_instance = fQueryASMInstance( tgt_host, tgt_port, tgt_user_grid, tgt_pass_grid, tgt_key_grid )
        if ( asm_instance == not_defined ): fa_pg_snap.mError( halt, 0, 'ASM not installed or running on host '+tgt_host )
        print( f'mounting ASM diskgroups on host {tgt_host} using ASM instance {asm_instance}' )

        # get the list of ASM diskgroups
        src_asm_diskgroups = fa_pg_ora_snap.dictDBParams.get( "asm_disk_groups" )

        # mount the ASM diskgroups on the target host
        lst_commands=[]
        lst_commands=["export ORAENV_ASK=NO; export ORACLE_SID="+asm_instance+"; . oraenv; asmcmd mount "+src_asm_diskgroups]
        fRemoteOSExecute( tgt_host, tgt_port, tgt_user_grid, tgt_pass_grid, tgt_key_grid, lst_commands )



    # verify the ASM diskgroups mounted on the target hosts
    mounted=0
    for tgt_host_next in lst_tgt_hosts:

        print( '============' )

        # get the next target rac host
        tgt_host = tgt_host_next["tgt_host"]

        # get the list of ASM diskgroups (e.g. DATA,FRA )
        src_asm_diskgroups = fa_pg_ora_snap.dictDBParams.get( "asm_disk_groups" )
        lst_src_asm_diskgroups = src_asm_diskgroups.split(',')

        # query the asm instance for this host
        asm_instance = fQueryASMInstance( tgt_host, tgt_port, tgt_user_grid, tgt_pass_grid, tgt_key_grid )
        if ( asm_instance == not_defined ): fa_pg_snap.mError( halt, 0, 'ASM not installed or running on host '+tgt_host )
        print( f'checking target ASM diskgroups are mounted {src_asm_diskgroups} on host {tgt_host}' )

        # check ASM for what is mounted
        lst_commands=[]
        lst_commands.append( "export ORAENV_ASK=NO; export ORACLE_SID="+asm_instance+"; . oraenv; asmcmd lsdg --suppressheader -g | grep 'MOUNTED' | awk -F' ' '{print $NF\",is mounted on node,\"$1}'" )
        lst_return=fRemoteOSExecute( tgt_host, tgt_port, tgt_user_grid, tgt_pass_grid, tgt_key_grid, lst_commands )

        # did we get any mounted diskgroups?
        for myreturn in lst_return:

            if ( "is mounted on node" in myreturn.strip()):

                #print( f'{myreturn.strip()}' )

                # each mounted diskgroup is a DG,NODE tuple
                myasmdg=myreturn.split(',')[0]
                myasmdg=myasmdg.rstrip("/")

                mynode=myreturn.split(',')[2]
                mynode=mynode.strip()

                # an ASM diskgroup used by the source database is mounted on one of the target nodes
                if( myasmdg in lst_src_asm_diskgroups ):
                    print( f'target ASM diskgroup {myasmdg} is mounted on node {tgt_host}' )
                    lst_src_asm_diskgroups.remove( myasmdg )

        # the lst_src_asm_diskgroups list should now be empty
        #print( f'{lst_src_asm_diskgroups}' )

        if( len( lst_src_asm_diskgroups )>0 ):
            mounted+=len( lst_src_asm_diskgroups )
            my_mounted_diskgroups=", ".join( lst_src_asm_diskgroups )

            print( f'ASM diskgroups {my_mounted_diskgroups} did not mount on node {tgt_host}' )

    if( mounted>0 ): fa_pg_snap.mError( halt, 0, 'target ASM diskgroups failed to mounted' )




    #
    # start the database
    # what is the required state?
    # down, started, mounted, open
    #

    # pull the first host from our list of target hosts
    print( '============'  )
    tgt_host=lst_tgt_hosts[0]["tgt_host"]

    print( f'requested state of {tgt_db} is:{ora_target_mode}' )

    if( ora_target_mode != "DOWN" ):

        # reset the SPFILE to match the source
        tgt_sid = mOraStartTargetRemote( tgt_host, tgt_port, tgt_user_oracle, tgt_pass_oracle, tgt_key_oracle, tgt_db, tgt_cs_db, "NOMOUNT", False )

        # reset the target SPFILE
        print( '============'  )
        mOraResetTargetSPFILERemote( tgt_host, tgt_port, tgt_user_oracle, tgt_pass_oracle, tgt_key_oracle, tgt_sid, tgt_cs_db )

        # shut down the target database to re-read the spfile
        mOraStopTargetRemote( tgt_host, tgt_port, tgt_user_oracle, tgt_pass_oracle, tgt_key_oracle, tgt_db )

        # restart the instance
        print( '============'  )
        print( f'restarting target database' )
        mOraStartTargetRemote( tgt_host, tgt_port, tgt_user_oracle, tgt_pass_oracle, tgt_key_oracle, tgt_db, tgt_cs_db, ora_target_mode, (True if fa_pg_ora_snap.dictDBParams.get( 'backup_mode' )=="Yes" else False ) )

        # check state of the target database
        caTargetOraStatus = 'DOWN'
        sql_result = fRemoteSQLExecute( tgt_host, tgt_port, tgt_user_oracle, tgt_pass_oracle, tgt_key_oracle, tgt_sid, tgt_cs_db, r"^RES:", ["select 'RES:'||decode(status,'STARTED','NOMOUNT','MOUNTED','MOUNT',status) \"-- command\" from v$instance;"] )

        mDebug( 3, f'target database state check:{sql_result}' )

        # fRemoteSQLExecute above will return a list, the first entry of which should be RES:STATE - we want the STATE
        try:
            caTargetOraStatus=sql_result[0].split(':')[1]
        except:
            caTargetOraStatus='DOWN'

        # if we are a container database....
        myres = fa_pg_ora_snap.dictDBParams.get( 'enable_pluggable_database', [] )
        if( myres=='TRUE' and ora_target_mode=='OPEN' ):

            print( 're-opening pluggable databases' )
            mOraStartPluggableRemote( tgt_host, tgt_port, tgt_user_oracle, tgt_pass_oracle, tgt_key_oracle, tgt_sid, tgt_cs_db, ora_target_mode )

        print( f'actual state of {tgt_sid} on host {tgt_host} is:{caTargetOraStatus.upper()}' )




    #
    # end of program
    #
    print( '============' )
    print( 'complete' )


if __name__ == "__main__": doMain()
