#
# Python script to snapshot a PG and optionally re-sync to a target PG
#
# Graham Thornton - May 2026
# gthornton@everpuredata.com
#
# requires py_pure_client
# requires python -m pip install 'setuptools<72.0.0'
#
# usage:
# python fa_pg_snap.py -s gct-oradb-vvol-ac::pgroup-auto -t gct-oradb-vvol-pg-swingtarget -n gct1 -f config.json -x
#

import sys
import time
import os
import re
import datetime
import json
import argparse

import warnings
warnings.filterwarnings(action='ignore')

from pypureclient import flasharray
import urllib3

from collections import defaultdict
from typing import NamedTuple

# global variables
HALT=1
NOHALT=0
I_BYTES_PER_GB = 1024**3

version = "1.2.0"
not_defined = "Not Defined"

# main dictionary for script variables
dictArgs={}

# dictionaries of souce and target volumes
# each dictionary uses id as key then a VolEntry tuple
dictSourceVols={}
dictTargetVols={}

# disable the HTTPS warnings
urllib3.disable_warnings()

from dataclasses import dataclass

@dataclass
class VolEntry:
    caMap:  str
    caName: str
    iSize:  int

#
# clean quit
#

def mQuit( message=None ):

    if( message is not None ):
        print( '============' )
        print( message )

    print( '============' )
    print( 'program terminated' )
    sys.exit( )

#
# generic error handler
#

def mError( my_halt, return_code, message ):
    print( '============' )
    print( f'error:{message}' )
    if( return_code !=0 ): print( f'return code:{return_code}' );

    # do we need to HALT execution?
    if( my_halt == HALT ): mQuit()


def fNotNone( foo, bar ):
    if foo is None: return bar
    return foo



##############################################

# JSON FILE PROCESSING

##############################################

#
# read json config file
#
def fReadConnectionJSON( myfile ):

    try:
        with open(myfile, 'r') as file:
            data = json.load(file)
            return data
    except FileNotFoundError:
        mQuit( f'Error: unable to open file: {myfile}' )

    except json.JSONDecodeError:
        mQuit( f'Error: invalid JSON format in :{myfile}' )


#
# json write
#
def mWriteConnectionJSON( myfile, mydict ):

    with open(myfile, "w") as file:
        json.dump(mydict, file, indent=4)



##############################################

# FLASH ARRAY

##############################################

#
# generic API call handler
#

def fAPICall( fn, message, **kwargs ):

    try:
        response = fn( **kwargs )

        if( response.status_code != 200 ):
            mError( HALT, response.status_code, response.errors[0].message )

        return response

    except Exception as e:

        mError( NOHALT, 0, f'{message}: {e}' )

        return None

#
# connect to the flash array
#

def fFAConnect( my_flash_array, my_flash_array_api_token, my_flash_array_api_version ):

    print( '============' )
    print( f'connecting to Flash Array:{my_flash_array} API Version:{my_flash_array_api_version}' )

    dict_client_args = {
        'target': my_flash_array,
        'api_token': my_flash_array_api_token,
    }

    if( my_flash_array_api_version is not None ):
        dict_client_args['version'] = my_flash_array_api_version

    try:

        array=flasharray.Client( **dict_client_args )

    except Exception as e:

        mError( HALT, 0, f'fFAConnect failed\nmessage:{e}\nplease check Flash Array connectivity and API token' )
        return None

    response = fAPICall( array.get_arrays, 'fFAConnect failed, please check Flash Array connectivity and API token' )
    if response is None: return None

    print( "connected" )
    return array

#
# get the name of the Flash Array - used for replication
#
def fFAQueryName( my_array ):

    response = fAPICall( my_array.get_arrays, 'call to get_arrays failed' )

    if response is None: return not_defined

    arrays = list(response.items)
    array_name = arrays[0].name
    return array_name

#
# check if the snapshot exists
#

def fQuerySnapExists( my_array, my_snapshot_name, my_protection_group ):

    print( '============' )
    print( f'determining if snapshot {my_snapshot_name} exists for protection group:{my_protection_group}' )

    response = fAPICall( 
        my_array.get_protection_group_snapshots, 
        'call to get_protection_group_snapshots failed',
        source_names=[my_protection_group]
    )

    for myoutput in response.items:

        #print( myoutput.suffix )

        if myoutput.suffix == my_snapshot_name:

            print( f'snapshot {my_snapshot_name} exists' )
            return True

    return False

#
# create the snapshot for the specified pg
#

def fCreateSnapshot( my_array, my_safe_mode, my_snapshot_name, my_protection_group, my_replicate, my_tag_pairs ):

    # build the tag objects from the (key, value) pairs passed in.
    # copyable=True is REQUIRED for the tags to travel with the snapshot
    # when it replicates to the target array.
    my_tags = [
        flasharray.Tag(
            namespace="default",
            key=str( my_key ),
            value=str( my_value ),
            copyable=True,
        )
        for my_key, my_value in my_tag_pairs
    ]

    # tag the snapshot with if it was replicated
    my_tags.append( flasharray.Tag( namespace="default", key="replicate", value=str(my_replicate), copyable=True ))

    #applied = ", ".join( f"{t.namespace} {t.key}={t.value}" for t in my_tags )
    #print(f"Tags applied: {applied}")

    print( '============' )
    print( f'creating snapshot for {my_protection_group}' )

    if( my_safe_mode ):

        print( f'NOTE: safety lock engaged - disable to create snapshot {my_snapshot_name}' )
        return ""

    else:

        snap_body = flasharray.ProtectionGroupSnapshotPost(
            suffix=my_snapshot_name,
            tags=my_tags,
        )

        #print( f'{snap_body}' )

        response = fAPICall( 
            my_array.post_protection_group_snapshots,
            'call to post_protection_group_snapshots failed',
            source_names=[my_protection_group],
            replicate=my_replicate,
            protection_group_snapshot=snap_body
        )

        # an empty name signals to the caller that no snapshot was created
        if response is None: return ""

    return my_snapshot_name


#
# return the list of volume names in the protection group
#

def fQueryVolsinPG( my_array, my_protection_group, my_array_name ):

    print( '============' )
    print( f'querying the volumes for protection group:{my_protection_group} on array {my_array_name}' )

    lst_my_vols=[]

    response = fAPICall( 
        my_array.get_protection_groups_volumes,
        'call to get_protection_groups_volumes failed',
        group_names=[my_protection_group] 
    )

    if response is None: return lst_my_vols

    # this returns a JSON doc of dictionaries

    for myoutput in response.items:

        lst_my_vols.append( myoutput.member['name'] )

        print( myoutput.member['name'] )

    return lst_my_vols


#
# query the list of volumes in the pg for the specified snapshot
# volumes found are added to dictSourceVols
#

def fQueryVolumesinSnapshot( my_array, my_protection_group, my_snapshot_name, lst_my_vols, lst_excluded_vols ):

    nVols=0
    print( '============' )
    print( f'listing the volumes for snapshot:{my_snapshot_name}' )

    # since this might be replicated the array might be prefixed so we pull all snapshots and inspect
    response = fAPICall( 
        my_array.get_volume_snapshots,
        'call to get_volume_snapshots failed'
    )

    for myoutput in response.items:

        # determine if this snapshot volume is part of our pg snapshot
        # snapshot volumes will be named for example:
        # sn1-x90r2-f05-27:gct-oradb-demo-prd01-pg.jun111653.gct-oradb-demo-prd01-fra-01
        # we will remove the volume name (the last section) and pass the remainder to 
        # fNameMatches

        if( fNameMatches( myoutput.name.rsplit( '.', 1 )[0], my_protection_group, my_snapshot_name )):

            # check if this volume is excluded from mapping
            if myoutput.source.id in lst_excluded_vols:
                print( f'id:{myoutput.source.id} is excluded from mapping' )
                print( f'  name:{myoutput.name}\n' )

            else:
                nVols+=1
                dictSourceVols[ myoutput.source.id ] = VolEntry( '0', myoutput.name, myoutput.space.total_provisioned )
                print( f'name:{myoutput.name} sz:{myoutput.space.total_provisioned/I_BYTES_PER_GB} GB' )


    return nVols

#
# query the target volumes specified in the given list
# the list is generated in fQueryVolsinPG and holds the names of the volumes in the target protection group
# for each volume check the size and if there is a source volume tag
# updates are written to dictTargetVols 
#

def mQueryTargetVolumeDetails( my_array, ignore_match, lst_my_vols ):

    print( '============' )
    print( 'querying target volume details' )

    # get the capacities of the volume list
    response = fAPICall(
        my_array.get_volumes_space,
        'call to get_volumes_space failed',
        names=lst_my_vols 
    )

    for myoutput in response.items:

        print( f'nm:{myoutput.name}\n  id:{myoutput.id}' )

        # check to see if this target volume has a source mapping
        # this is stored as a kv tag on the target volume snapshot_mapping:id
        # where id is the source volume that will map to this target
        src_map='0'

        response2 = fAPICall(
            my_array.get_volumes_tags,
            'call to get_volumes_tags failed',
            resource_names=[myoutput.name] 
        )

        # there is a tag
        for myoutput2 in response2.items:

            #print( myoutput2.key )
            #print( myoutput2.value )

            # is this tag a mapping?
            if( not ignore_match and myoutput2.key == 'snapshot_mapping' ):

                # myoutput2.value is the value of the kv tag
                # and is the volume ID of the matching source
                src_map = myoutput2.value

                # for the value, check if it is a valid volume id in the source dictionary
                # if so, this will return a tupple: tmap|name|size
                if( (src_val := dictSourceVols.get( src_map )) is not None ):
                    src_name = src_val.caName
                    src_size_gb = src_val.iSize / I_BYTES_PER_GB
                    print( f'  is a target for {src_name}\n  sz:{src_size_gb} GB' )


        # update the target dictionary with the source mapping, name and size in bytes of this volume id
        dictTargetVols[ myoutput.id ] = VolEntry( src_map, myoutput.name, myoutput.space.total_provisioned ) 


#
# read through dictSourceVols for when tmap is not set
# then read dictTargetVols for a target volume (tmap=source id)
# if not found, see if there is a target volume with no tmap and a matching size
# if not found, see if there is a target volume with no tamp and a larger size
# the purpose of this is to tag target volumes with the id of the source
# so that every subsequent execution maps the same source to the same target
#

def fCreateVolumeMap( ):

    print( '============' )
    print( 'determining volume mapping' )

    nUnmatched=0

    for src_key, src_val in dictSourceVols.items():
        src_tmap = src_val.caMap
        src_name = src_val.caName
        src_size = src_val.iSize

        print( f'nm:{src_name}\n  src id:{src_key} map:{src_tmap}\n  sz:{src_size/I_BYTES_PER_GB} GB' )

        # if this src vol is not matched, is there a tagged target for this volume?
        if( src_tmap=='0' ):

            print( '  checking for tag matched volume' )

            for tgt_key, tgt_val in dictTargetVols.items():
                tgt_smap = tgt_val.caMap
                tgt_name = tgt_val.caName
                tgt_size = tgt_val.iSize

                #print( f'    tgt key:{tgt_key} smap:{tgt_smap} nm:{tgt_name} sz:{tgt_size/I_BYTES_PER_GB}' )

                # if the targets smap matched source id
                if( tgt_smap==src_key ):
                    print( f'  will be synced to {tgt_name}' )
                    dictSourceVols[ src_key ] = VolEntry( tgt_key, src_name, src_size )
                    dictTargetVols[ tgt_key ] = VolEntry( src_key, tgt_name, tgt_size )

                    src_tmap=tgt_key
                    break


        # if this src vol is not matched, is there an unmatched target of equal size?
        if( src_tmap=='0' ):

            print( '  checking for unmatched volume of equal size' )

            # is there a matching target for this volume?
            for tgt_key, tgt_val in dictTargetVols.items():
                tgt_smap = tgt_val.caMap
                tgt_name = tgt_val.caName
                tgt_size = tgt_val.iSize

                print( f'    tgt key:{tgt_key} smap:{tgt_smap} nm:{tgt_name} sz:{int(tgt_size)/I_BYTES_PER_GB} GB' )

                if( tgt_smap=='0' and tgt_size==src_size ):
#                    print( 'volume '+src_name+' will be synced to '+tgt_name )
                    dictSourceVols[ src_key ] = VolEntry( tgt_key, src_name, src_size )
                    dictTargetVols[ tgt_key ] = VolEntry( src_key, tgt_name, tgt_size )

                    src_tmap=tgt_key
                    break



        # if this src vol is not matched, is there an unmatched target of larger size?
        if( src_tmap=='0' ):

            print( '  checking for unmatched volume of larger size' )

            # is there a matching target for this volume?
            for tgt_key, tgt_val in dictTargetVols.items():
                tgt_smap = tgt_val.caMap
                tgt_name = tgt_val.caName
                tgt_size = tgt_val.iSize

#                print( '    tgt key:'+tgt_key+' smap:'+tgt_smap+' nm:'+tgt_name+' sz:'+tgt_size )

                if( tgt_smap=='0' and tgt_size>=src_size ):
#                   print( 'volume '+src_name+' will be synced to '+tgt_name )
                    dictSourceVols[ src_key ] = VolEntry( tgt_key, src_name, src_size )
                    dictTargetVols[ tgt_key ] = VolEntry( src_key, tgt_name, tgt_size )
                    src_tmap=tgt_key
                    break

        # catch a no-match
        if( src_tmap=='0' ):

            nUnmatched+=1
            print( '  no matching target volume found' )


    # how many volumes were we unable to match
    return nUnmatched


#
# check replication status and waits in a loop until it is done
#
def fQuerySnapshotReplication( my_array, my_array_name, my_protection_group, my_snapshot_name, my_repeat, my_sleep, my_safe_mode ):

    def fQuerySnapshotReplicationSub( my_array, my_target ):

        response = fAPICall( 
            my_array.get_protection_group_snapshots_transfer,
            'call to get_protection_group_snapshots_transfer failed',
            names=[my_target] 
        )

        if response is None: return None

        try:
            data = list(response.items)
            return data[0].progress
        except ( IndexError, TypeError ):
            return None

    if( my_safe_mode ): return True

    # build the name of the target snapshot to look for 
    # it will be src_array_name:src_pg:snapname
    my_target = my_array_name+':'+my_protection_group+'.'+my_snapshot_name

    print( '============' )
    print( 'waiting on snapshot replication' )

    nCount=0
    retval=False
    while( nCount<my_repeat ):
        nCount+=1
        progress = fQuerySnapshotReplicationSub( my_array, my_target )
        if progress is not None and float(progress) >= 1.0:
            retval=True
            break
        print( ".", end="", flush=True )
        time.sleep(my_sleep)

    if( retval ): print( "\nreplication complete" )
    else: print( "\nreplication wait timed out" )

    return retval
    
#
# process the dictSourceVols and then fetch the matching volume from dictTargetVols
# use the REST API call to sync the target to the source snapshot volume
#

def mMapVolumes( my_array, my_safe_mode ):
    
    print( '============' )
    print( 'mapping the volumes' )

    for src_key, src_val in dictSourceVols.items():
        src_tmap = src_val.caMap
        src_name = src_val.caName
        src_size = src_val.iSize
        #src_tmap, src_name, src_size = src_val

        print( f'{src_name}\n  src key:{src_key}\n  map:{src_tmap}' )

        # get the matching target

        tgt_val = dictTargetVols.get( src_tmap )
        if( tgt_val is not None ):
            tgt_name = tgt_val.caName
            tgt_size = tgt_val.iSize

            print( f'  will be syncd to {tgt_name}' )

            myvol={
                'source': {'name': src_name },
                'provisioned': src_size 
            }

            if( src_size != tgt_size ):
                print( f'target volume will be resized from {int(tgt_size)/I_BYTES_PER_GB} GB to match source source volume sz:{int(src_size)/I_BYTES_PER_GB} GB' )

            if( my_safe_mode ):

                print( 'NOTE: safety lock engaged - disable to sync the target volume' )

            else:

                response = fAPICall( 
                    my_array.post_volumes,
                    'call to post_volumes failed',
                    names=[tgt_name], overwrite=True, volume=myvol 
                )

                # record the mapping so that when we refresh, the same disks map to the same volumes
                kv={
                    'key': 'snapshot_mapping',
                    'value': src_key,
                }

                response2 = fAPICall( 
                    my_array.put_volumes_tags_batch,
                    'call to put_volumes_tags_batch failed',
                    resource_names=[tgt_name], tag=[kv]
                )

        else:
            print( 'WARNING: there is no mapping for '+src_name )


#
# write the volumes found in the snapshot to the specified file
#

def mWriteVolumesinSnapshot( output_file, lst_excluded_vols ):

    print( '============' )

    try:

        with open(output_file, "w") as f:

            print( f'writing the snapshot list to:{output_file}' )

            for src_key, src_val in dictSourceVols.items():

                if src_key in lst_excluded_vols:
                    print( f'vol:{src_val.caName} is excluded from output file' )
                else:
                    print( f'vol:{src_val.caName}' )
                    f.write( src_val.caName+'\n' )

    except OSError as e:
        mError( NOHALT, 0, f'unable to write to {output_file}: {e}' )


##############################################

# TAG PROCESSING

##############################################

#True if snap_name is the local or a replicated form of my_protection_group.my_suffix.

def fNameMatches(snap_name, my_protection_group, my_suffix):

    target = f"{my_protection_group}.{my_suffix}"
    return snap_name == target or snap_name.endswith(f":{target}")


def fFindMatchingSnapshots(my_array, my_protection_group, my_suffix):
    """Page through all pg snapshots and return names matching my_protection_group.my_suffix.

    Works for replicated snapshots because matching is done on the snapshot
    name (which carries the source-array prefix), not on a local my_protection_group object.
    """
    lst_matches = []
    continuation_token = None

    while True:

        response = fAPICall( 
            my_array.get_protection_group_snapshots,
            'call to get_protection_group_snapshots failed',
             continuation_token=continuation_token
        )

        items = list(response.items)
        for snap in items:
            if fNameMatches(snap.name, my_protection_group, my_suffix):
                lst_matches.append(snap.name)

        # Advance pagination, if the SDK surfaced a continuation token.
        continuation_token = getattr(response, "continuation_token", None)
        if not continuation_token:
            break

    return lst_matches

def fResourceNameOf( my_tag ):
    """Best-effort extraction of the snapshot name a tag belongs to."""
    resource = getattr(my_tag, "resource", None)
    if resource is None:
        return None
    if isinstance(resource, dict):
        return resource.get("name")
    return getattr(resource, "name", None)

class SnapshotTag(NamedTuple):
    namespace: str 
    key: str 
    value: str

# for a given protection group and snapshot name
# read the tags and return it as a list of tupes (namespace, key value)

def fQuerySnapshotTags( my_array, my_protection_group, my_snapshot_name ):

    lst_snapshots = fFindMatchingSnapshots( my_array, my_protection_group, my_snapshot_name )

    if not lst_snapshots: mQuit( "snapshot exists but no matching snapshot found" )

    #print( f'{lst_snapshots}' )
    response = fAPICall( 
        my_array.get_protection_group_snapshots_tags,
        'call to get_protection_group_snapshots_tags failed',
        resource_names=lst_snapshots 
    )

    #print( f'{response}' )

    tags_by_snapshot = defaultdict(list)

    for tag in response.items: tags_by_snapshot[fResourceNameOf(tag)].append(tag)

    #print( f'tags by snapshot:{tags_by_snapshot}' )

    lst_return=[]
    for snap_name in lst_snapshots:
        snap_tags = tags_by_snapshot.get(snap_name, [])
        if snap_tags:
            print(f"tags for {snap_name}:")
            for tag in snap_tags:
                #print(f"  [{tag.namespace}] {tag.key}={tag.value}")
                lst_return.append( SnapshotTag( tag.namespace, tag.key, tag.value ))


        else:
            print(f"snapshot {snap_name} not found")

    #print( f'{lst_return}' )
    return lst_return

##############################################

# MAIN BLOCK

##############################################

def doMain( ):

    # parse the command line args
    parser = argparse.ArgumentParser(
                    prog='fa_pg_snap ', usage='%(prog)s [-s -t -n -f -i -r -o -x -h]',
                    description='snapshot a protection group on an Everpure Flash Array',
                    epilog='coded by Graham Thornton - gthornton@everpuredata.com')

    parser.add_argument('-s','--caSourceProtectionGroup', help='source pg', required=False)
    parser.add_argument('-t','--caTargetProtectionGroup', help='target pg', required=False)
    parser.add_argument('-n','--snapshot_name', help='name of the snapshot', required=True)
    parser.add_argument('-f','--config_file', help='json document of config options', required=False)
    parser.add_argument('-i','--ignore_match', action='store_true', help='ignore tag-matching')
    parser.add_argument('-r','--replicate', action='store_true', help='replicate the snapshot')
    parser.add_argument('-o','--output_file', help='output file with names of volumes in the snapshot', required=False)
    parser.add_argument('-x','--execute_lock', action='store_false', help="specify -x to actually snap the pg (default is safety lock on)") 

    args = parser.parse_args()


    print( '============' )
    print( f'fa_pg_snap.py {version} started at {datetime.datetime.now()}' )

    snapshot_name=args.snapshot_name
    source_snap_exists=False


    #
    # read the config file
    #
    if( args.config_file != None ): dictArgs = fReadConnectionJSON( args.config_file )

    # fa variables for source array
    src_flash_array = dictArgs.get( "src_flash_array_host", dictArgs.get( "flash_array_host", os.environ.get('FA_HOST')))
    src_flash_array_api_token = dictArgs.get( "src_flash_array_api_token", dictArgs.get( "flash_array_api_token", os.environ.get('API_TOKEN')))
    flash_array_api_version = dictArgs.get( "flash_array_api_version" )

    if( src_flash_array==None or src_flash_array_api_token==None ):
        mQuit( 'src_flash_array_host and src_flash_array_api_token need to be defined in the config file or environment variables' )

    #
    # connect to the source FA
    #
    myArraySrc = fFAConnect( src_flash_array, src_flash_array_api_token, flash_array_api_version )
    src_array_name = fFAQueryName( myArraySrc )


    #
    # get the source and optional target protection groups
    #
    caSourceProtectionGroup=fNotNone( args.caSourceProtectionGroup, dictArgs.get( "caSourceProtectionGroup", dictArgs.get( "src_protection_group", not_defined )))
    caTargetProtectionGroup=fNotNone( args.caTargetProtectionGroup, dictArgs.get( "caTargetProtectionGroup", dictArgs.get( "tgt_protection_group", not_defined )))
    if( caSourceProtectionGroup==not_defined ): mQuit( 'source protection group is not defined' )

    #
    # check if we want the snapshot to replicate
    #
    bReplicate = ( args.replicate or dictArgs.get( "replicate" )=="True" )

    #
    # do we want to replicate this snapshot?
    #
    if( bReplicate ):

        if( caSourceProtectionGroup==not_defined ): mQuit( 'replicate specified but source protection group is not defined' )

        # fa variables for target array
        tgt_flash_array = dictArgs.get( "tgt_flash_array_host", os.environ.get('FA_HOST_TGT') )
        tgt_flash_array_api_token = dictArgs.get( "tgt_flash_array_api_token", os.environ.get('API_TOKEN_TGT') )

        if( tgt_flash_array==None or tgt_flash_array_api_token==None ):
            mQuit( 'tgt_flash_array_host and tgt_flash_array_api_token need to be defined in the config file or environment variables' )

        #
        # connect to the target FA
        #
        myArrayTgt = fFAConnect( tgt_flash_array, tgt_flash_array_api_token, flash_array_api_version )
        tgt_array_name = fFAQueryName( myArrayTgt )

        
        #
        # check the source PG is set for replication
        #
        my_protection_group=[caSourceProtectionGroup]
     
        response = myArraySrc.get_protection_groups( names=my_protection_group )
        for item in response.items: 
            #print ( item.target_count )
            if( item.target_count==0 ): mQuit( 'source protection group is not set for replication' )
        
    else:

        myArrayTgt = myArraySrc
        tgt_array_name = src_array_name


    #
    # check if the source pg has the requested snapshot
    #
    source_snap_exists=fQuerySnapExists( myArraySrc, snapshot_name, caSourceProtectionGroup )


    print( f'source protection group:{caSourceProtectionGroup}' )
    print( f'target protection group:{caTargetProtectionGroup}' )


    #
    # query the volumes of the source pg
    # these are collected in lst_source_vols
    # we verify PG existance before making the snapshot
    #
    lst_source_vols = fQueryVolsinPG( myArraySrc, caSourceProtectionGroup, src_array_name )


    #
    # if the snapshot does not exist create it
    # if safety lock engaged this will return a null string
    #
    if( not source_snap_exists ): 

        snapshot_name=fCreateSnapshot( 
            myArraySrc, 
            args.execute_lock, 
            snapshot_name, 
            caSourceProtectionGroup, 
            bReplicate, 
            [] 
        )

    else:

        print( '============' )
        print( 'reading tags from snapshot' )

        lst_tags = fQuerySnapshotTags( myArraySrc, caSourceProtectionGroup, snapshot_name )

        for tag in lst_tags:

            print( f'key:{tag.key} value:{tag.value}' )
            if( tag.key == "replicate" ):
                
                if( bReplicate and str(bReplicate) != tag.value ):

                    mQuit( "existing snapshot was not replicated" )



    #
    # did we create snapshot?
    # this allows us to come out of backup mode on the source if safety lock engaged
    # and didnt create a snapshot
    #
    if ( snapshot_name=="" ): mQuit()



    #
    # get any excluded volumes - VVOL config volumes need to be excluded
    #
    print( '============' )
    lst_excluded_vols = dictArgs.get( "excluded_volumes", [] )
    for vol in lst_excluded_vols: print( f'excluding:{vol}' )



    #
    # query the snapshots of the volumes in the source pg
    # these are recorded in dictSourceVols( id:target_map|vol_name|size_in_bytes )
    # entries found in the exclude file will be omitted
    #
    fQueryVolumesinSnapshot( myArrayTgt, caSourceProtectionGroup, snapshot_name, lst_source_vols, lst_excluded_vols )


    #
    # if an output file was specified, then write the volume names to it
    #
    if( args.output_file != None ):
        print( '============' )
        lst_excluded_vols = dictArgs.get( "excluded_volumes", [] )
        mWriteVolumesinSnapshot( args.output_file, lst_excluded_vols )


    #
    # if not target PG was define we stop here
    #
    if caTargetProtectionGroup==not_defined: mQuit( )



    #
    # query the volumes of the target pg
    # collect these in lst_target_vols
    #
    lst_target_vols = fQueryVolsinPG( myArrayTgt, caTargetProtectionGroup, tgt_array_name )


    #
    # for each target volume get the capacity and the source volume id
    # this call populates dictTargetVols id:source_map|vol_name|size
    #
    mQueryTargetVolumeDetails( myArrayTgt, args.ignore_match, lst_target_vols )


    #
    # process the source volume dictionary and see if there are suitable matches in the target volume dictionary
    # we process the dictSource looking for volumes where the tmap is not set
    # we then look for a match in dictTarget
    # when found we update dictSource tmap
    #
    fCreateVolumeMap( )


    #
    # if replication is specified check the snapshot replicated
    #
    if( bReplicate ):    
        retval = fQuerySnapshotReplication( myArrayTgt, src_array_name, caSourceProtectionGroup, snapshot_name, 10, 5, args.execute_lock )
        if( retval==False ):
            mError( HALT, 0, 'snapshot replication did not complete in the time allowed' )

    #
    # process the dictSourceVols and then fetch the matching volume from dictTargetVols
    #
    mMapVolumes( myArrayTgt, args.execute_lock )



    #
    # end of program
    #
    print( '============' )
    print( 'complete' )


if __name__ == "__main__": doMain()



