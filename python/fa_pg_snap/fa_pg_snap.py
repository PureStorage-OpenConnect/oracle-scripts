#
# Python script to snapshot a PG and optionally re-sync to a target PG
#
# Graham Thornton - July 2025
# gthornton@purestorage.com
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


# global variables
halt=1
nohalt=0
version = "1.0.0"
not_defined = "Not Defined"

# main dictionary for script variables
dictArgs={}

# dictionaries of souce and target volumes
# each dictionary uses id as key then volname|size
# dictTargetVols also might have a 3rd datum which is the source vol id
dictSourceVols={}
dictTargetVols={}

# disable the HTTPS warnings
urllib3.disable_warnings()

#
# clean quit
#

def mQuit( message=None ):

    if( message != None ):
        print( '============' )
        print( message )

    print( '============' )
    print( 'program terminated' )
    quit()

#
# generic error handler
#

def mError( halt, return_code, message ):
    print( '============' )
    print( f'error:{message}' )
    if( return_code !=0 ): print( f'return code:{return_code}' );

    # do we need to halt execution?
    if( halt>0 ): mQuit()


def fNotNone( foo, bar ):
    if foo==None: return bar
    return foo

def fDictBool( key, default_bool ):
    rbool = default_bool
    xx = dictArgs.get ( key, not_defined )
    if( xx=="True" ): rbool=True
    if( xx=="False" ): rbool=False
    return rbool

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
        print(f'Note: file not found:{myfile}')
        return None
    except json.JSONDecodeError:
        print(f'Error: Invalid JSON format in:{myfile}')
        return None


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
# connect to the flash array
#

def fFAConnect( my_flash_array, my_flash_array_api_token ):

    print( '============' )
    print( f'connecting to Flash Array:{my_flash_array}' )

    try:
        array=flasharray.Client( target=my_flash_array, api_token=my_flash_array_api_token )

        response = array.get_volumes()

        if ( response.status_code == 200): print( "connected" )
        else: mError( halt, response.status_code, response.reason )

    except:
        mError( halt, 0, 'fFAConnect failed, please check Flash Array connectivity and API token' )

    return array


#
# check if the snapshot exists
#

def fQuerySnapExists( my_array, my_snapshot_name, my_protection_group ):

    print( '============' )
    print( f'determining if snapshot {my_snapshot_name} exists for source pg:{my_protection_group}' )

    try:
        response = my_array.get_protection_group_snapshots( source_names=[my_protection_group] )

    except:
        mError( halt, 0, 'call to get_protection_group_snapshots failed' )

    if ( response.status_code != 200 ):
        #print( response.errors[0] )
        #print( response.errors[0].message )

        #mError( halt, response.status_code, 'protection group snapshot failed' )
        mError( halt, response.status_code, response.errors[0].message )

    for myoutput in response.items:

        #print( myoutput.suffix )

        if myoutput.suffix == my_snapshot_name:

            print( f'snapshot {myoutput.suffix} exists' )
            return True

    return False

#
# create the snapshot for the specified pg
#

def fCreateSnapshot( my_array, my_safe_mode, my_snapshot_name, my_protection_group, my_replicate ):

    mydoc={
        'eradication_config': {'manual_eradication': 'enabled'},
        'replicate': my_replicate,
        'suffix': my_snapshot_name
    }


    print( '============' )
    print( f'creating snapshot for {my_protection_group}' )

    if( my_safe_mode ):

        print( f'NOTE: safety lock engaged - disable to create snapshot {my_snapshot_name}' )
        return ""

    else:

        try:
            response = my_array.post_protection_group_snapshots( source_names=[my_protection_group], protection_group_snapshot=mydoc )

        except:
            mError( halt, 0, 'call to post_protection_group_snapshots' )

        if ( response.status_code != 200 ): mError( halt, response.status_code, response.errors[0].message )


    return my_snapshot_name


#
# return the list of volume names in the protection group
#

def fQueryVolsinPG( my_array, my_protection_group ):

    print( '============' )
    print( f'querying the volumes for protection group:{my_protection_group}' )

    lst_my_vols=[]

    try:
        response = my_array.get_protection_groups_volumes( group_names=[my_protection_group] )
    except:
        mError( halt, 0, 'call to get_protection_groups_volumes failed' )

    if ( response.status_code != 200 ): mError( halt, response.status_code, response.errors[0].message )

    # this returns a JSON doc of dictionaries

    for myoutput in response.items:

        lst_my_vols.append( myoutput.member['name'] )

        print( myoutput.member['name'] )
        # print( myoutput.member['id'] )

    return lst_my_vols


#
# query the list of volumes in the pg for the specified snapshot
#

def fQueryVolumesinSnapshot( my_array, my_protection_group, my_snapshot_name, lst_my_vols, lst_excluded_vols ):

    nVols=0
    print( '============' )
    print( f'listing the volumes for snapshot:{my_snapshot_name}' )

    # since this might be replicated the array might be prefixed so we pull all snapshots and inspect
    try:
        response = my_array.get_volume_snapshots( )
    except:
        mError( halt, 0, 'call to get_volume_snapshots failed' )

    if ( response.status_code != 200 ): mError( halt, response.status_code, 'call to get_volume_snapshots failed' )

    for myoutput in response.items:

        #print( myoutput )
        #print( myoutput.name )
        if( my_protection_group+'.'+my_snapshot_name in myoutput.name ):

            # check if this volume is excluded from mapping
            if myoutput.source.id in lst_excluded_vols:
                print( f'id:{myoutput.source.id} is excluded from mapping' )
                print( f'  name:{myoutput.name}\n' )

            else:
                nVols+=1
                dictSourceVols.update({ myoutput.source.id: '0|'+myoutput.name+'|'+str(myoutput.space.total_provisioned) })
                print( f'name:{myoutput.name} size:{myoutput.space.total_provisioned/1073741824} GB' )


    return nVols

#
# query the target volumes specified in the given list
# for each volume check the size and if there is a source volume tag
#

def mQueryTargetVolumeDetails( my_array, ignore_match, lst_my_vols ):

    print( '============' )
    print( 'querying target volume details' )

    # get the capacities of the volume list
    response = my_array.get_volumes_space( names=lst_my_vols )
    for myoutput in response.items:

        print( f'name:{myoutput.name} id:{myoutput.id} size:{myoutput.space.total_provisioned/1073741824}' )

        # check to see if this target volume has a source mapping
        # this is stored as a kv tag on the target volume snapshot_mapping:id
        # where id is the source volume that will map to this target
        src_map='0'
        response2 = my_array.get_volumes_tags( resource_names=[myoutput.name] )

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
                src_val = dictSourceVols.get( src_map, "not_present" )
                if( src_val != 'not_present' ):
                    lst_src_vals = src_val.split( '|' )
                    src_name = lst_src_vals[1]
                    src_size_gb = int(lst_src_vals[2])/1073741824

                    print( f'   is a target for {src_name} size:{src_size_gb} GB' )

        # update the target dictionary with the source mapping, name and size in bytes of this volume id
        dictTargetVols.update({ myoutput.id: src_map+'|'+myoutput.name+'|'+str(myoutput.space.total_provisioned) })


#
# read through dictSourceVols for when tmap is not set
# then read dictTargetVols for a target volume (tmap=source id)
# if not found, see if there is a target volume with no tmap and a matching size
# if not found, see if there is a target volume with no tamp and a larger size
#

def fCreateVolumeMap( ):

    print( '============' )
    print( 'determining volume mapping' )

    unmatched=0

    for i, (src_key, src_val) in enumerate(dictSourceVols.items()):

        lst_src_vals = src_val.split( '|' )
        src_tmap = lst_src_vals[0]
        src_name = lst_src_vals[1]
        src_size = lst_src_vals[2]

        print( f'nm:{src_name} src id:{src_key} map:{src_tmap} sz:{int(src_size)/1073741824}' )

        # if this src vol is not matched, is there a tagged target for this volume?
        if( src_tmap=='0' ):

            print( '  checking for tag matched volume' )

            for i2, (tgt_key, tgt_val) in enumerate(dictTargetVols.items()):

                lst_tgt_vals = tgt_val.split( '|' )
                tgt_smap = lst_tgt_vals[0]
                tgt_name = lst_tgt_vals[1]
                tgt_size = lst_tgt_vals[2]

                #print( f'    tgt key:{tgt_key} smap:{tgt_smap} nm:{tgt_name} sz:{tgt_size/1073741824}' )

                # if the targets smap matched source id
                if( src_tmap=='0' and tgt_smap==src_key ):
                    print( f'    volume {src_name} will be synced to {tgt_name}' )
                    dictSourceVols.update({ src_key: tgt_key+'|'+src_name+'|'+src_size })
                    dictTargetVols.update({ tgt_key: src_key+'|'+tgt_name+'|'+tgt_size })
                    src_tmap=tgt_key


        # if this src vol is not matched, is there an unmatched target of equal size?
        if( src_tmap=='0' ):

            print( '  checking for unmatched volume of equal size' )

            # is there a matching target for this volume?
            for i2, (tgt_key, tgt_val) in enumerate(dictTargetVols.items()):

                lst_tgt_vals = tgt_val.split( '|' )
                tgt_smap = lst_tgt_vals[0]
                tgt_name = lst_tgt_vals[1]
                tgt_size = lst_tgt_vals[2]

                print( f'    tgt key:{tgt_key} smap:{tgt_smap} nm:{tgt_name} sz:{int(tgt_size)/1073741824}' )

                if( src_tmap=='0' and tgt_smap=='0' and int(tgt_size)==int(src_size) ):
#                    print( 'volume '+src_name+' will be synced to '+tgt_name )
                   dictSourceVols.update({ src_key: tgt_key+'|'+src_name+'|'+src_size })
                   dictTargetVols.update({ tgt_key: src_key+'|'+tgt_name+'|'+tgt_size })
                   src_tmap=tgt_key



        # if this src vol is not matched, is there an unmatched target of larger size?
        if( src_tmap=='0' ):

            print( '  checking for unmatched volume of larger size' )

            # is there a matching target for this volume?
            for i2, (tgt_key, tgt_val) in enumerate(dictTargetVols.items()):

                lst_tgt_vals = tgt_val.split( '|' )
                tgt_smap = lst_tgt_vals[0]
                tgt_name = lst_tgt_vals[1]
                tgt_size = lst_tgt_vals[2]

#                print( '    tgt key:'+tgt_key+' smap:'+tgt_smap+' nm:'+tgt_name+' sz:'+tgt_size )

                if( src_tmap=='0' and tgt_smap=='0' and int(tgt_size)>=int(src_size) ):
#                   print( 'volume '+src_name+' will be synced to '+tgt_name )
                    dictSourceVols.update({ src_key: tgt_key+'|'+src_name+'|'+src_size })
                    dictTargetVols.update({ tgt_key: src_key+'|'+tgt_name+'|'+tgt_size })
                    src_tmap=tgt_key

        # catch a no-match
        if( src_tmap=='0' ):

            unmatched+=1
            print( '  no matching target volume found' )


    # how many volumes were we unable to match
    return unmatched



#
# process the dictSourceVols and then fetch the matching volume from dictTargetVols
# use the REST API call to sync the target to the source snapshot volume
#

def fMapVolumes( my_array, my_safe_mode ):

    print( '============' )
    print( 'mapping the volumes' )

    for i, (src_key, src_val) in enumerate(dictSourceVols.items()):

        lst_src_vals = src_val.split( '|' )
        src_tmap = lst_src_vals[0]
        src_name = lst_src_vals[1]
        src_size = lst_src_vals[2]

        #print( f'src key:{src_key} map:{src_tmap} nm:{src_name} sz:{src_size}' )

        # get the matching target
        tgt_val = dictTargetVols.get( src_tmap )

        if( tgt_val != None ):

            lst_tgt_vals = tgt_val.split( '|' )
            tgt_name = lst_tgt_vals[1]
            tgt_size = lst_tgt_vals[2]
            print( f'{src_name} will be syncd to {tgt_name}' )

            myvol={
                'source': {'name': src_name },
            }

            if( src_size > tgt_size ):
                print( 'ERROR: source volume is larger than target volume' )
                print( f'ERROR: source volume size:{src_size}' )
                print( f'ERROR: target volume size:{tgt_size}' )

            elif( my_safe_mode ):

                print( 'NOTE: safety lock engaged - disable to sync the target volume' )

            else:
                try:
                    response = my_array.post_volumes( names=[tgt_name], overwrite=True, volume=myvol )
                except:
                    mError( halt, 0, 'call to post_volumes failed' )

                #if ( response.status_code != 200 ): mError( halt, response.status_code, response.errors[0].message )
                if ( response.status_code != 200 ): return response.errors[0].message 

                # record the mapping so that when we refresh, the same disks map to the same volumes
                kv={
                    'key': 'snapshot_mapping',
                    'value': src_key,
                }

                try:
                    response = my_array.put_volumes_tags_batch( resource_names=[tgt_name], tag=[kv] )
                except:
                    mError( halt, 0, 'call to put_volumes_tags_batch failed' )

        else:
            print( 'NOTE: there is no mapping for '+src_name )

    return ""

#
# write the volumes found in the snapshot to the specified file
#

def mWriteVolumesinSnapshot( output_file, lst_excluded_vols ):

    print( '============' )

    try:
        f = open(output_file, "w")
        print( f'writing the snapshot list to:{output_file}' )
    except:
        output_file=''
        mError( nohalt, 0, 'unable to write to '+output_file )

    for i, (key, val) in enumerate(dictSourceVols.items()):

        lst_vals = val.split( '|' )
        tmap = lst_vals[0]
        name = lst_vals[1]
        size = lst_vals[2]

        #print( 'id:'+key+' map:'+tmap+' nm:'+name+' sz:'+size )
        if key in lst_excluded_vols:
            print( f'vol:{name} is excluded from output file' )
        else:
            print( f'vol:{name}' )
            if( len(output_file)>0 ): f.write( name+'\n' )

    if( len(output_file)>0 ): f.close()


##############################################

# MAIN BLOCK

##############################################

def doMain( ):

    # parse the command line args
    parser = argparse.ArgumentParser(
                    prog='fa_pg_snap ', usage='%(prog)s [-s -t -n -f -i -r -o -x -h]',
                    description='snapshot a protection group on a Pure Flash Array',
                    epilog='coded by Graham Thornton - gthornton@purestorage.com')

    parser.add_argument('-s','--source_protection_group', help='source pg', required=False)
    parser.add_argument('-t','--target_protection_group', help='target pg', required=False)
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
    dictArgs={}
    if( args.config_file != None ): dictArgs = fReadConnectionJSON( args.config_file )

    # fa variables for source array
    src_flash_array = dictArgs.get( "src_flash_array_host", os.environ.get('FA_HOST') )
    src_flash_array_api_token = dictArgs.get( "src_flash_array_api_token", os.environ.get('API_TOKEN') )

    if( src_flash_array==None or src_flash_array_api_token==None ):
        mQuit( 'src_flash_array_host and src_flash_array_api_token need to be defined in the config file or environment variables' )

    #
    # connect to the source FA
    #
    myArraySrc = fFAConnect( src_flash_array, src_flash_array_api_token )


    #
    # get the source and optional target protection groups
    #
    source_protection_group=fNotNone( args.source_protection_group, dictArgs.get( "source_protection_group", not_defined ))
    target_protection_group=fNotNone( args.target_protection_group, dictArgs.get( "target_protection_group", not_defined ))


    #
    # do we want to replicate this snapshot?
    #
    if( args.replicate ):

        if( source_protection_group==not_defined ): mQuit( 'replicate specified but source protection group is not defined' )

        # fa variables for target array
        tgt_flash_array = dictArgs.get( "tgt_flash_array_host", os.environ.get('FA_HOST_TGT') )
        tgt_flash_array_api_token = dictArgs.get( "tgt_flash_array_api_token", os.environ.get('API_TOKEN_TGT') )

        if( tgt_flash_array==None or tgt_flash_array_api_token==None ):
            mQuit( 'tgt_flash_array_host and tgt_flash_array_api_token need to be defined in the config file or environment variables' )

        #
        # connect to the target FA
        #
        myArrayTgt = fFAConnect( tgt_flash_array, tgt_flash_array_api_token )

        
        #
        # check the source PG is set for replication
        #
        my_protection_group=[source_protection_group]
     
        response = myArraySrc.get_protection_groups( names=my_protection_group )
        for item in response.items: 
            #print ( item.target_count )
            if( item.target_count==0 ): mQuit( 'source protection group is not set for replication' )
        
    else:

        myArrayTgt = myArraySrc



    #
    # check if the source pg has the requested snapshot
    #
    source_snap_exists=fQuerySnapExists( myArraySrc, snapshot_name, source_protection_group )


    print( f'source protection group:{source_protection_group}' )
    print( f'target protection group:{target_protection_group}' )


    #
    # query the volumes of the source pg
    # these are collected in lst_source_vols
    # we verify PG existance before making the snapshot
    #
    lst_source_vols = fQueryVolsinPG( myArraySrc, source_protection_group )

    if target_protection_group!=not_defined: 

        #
        # query the volumes of the target pg
        # collect these in lst_target_vols
        #
        lst_target_vols = fQueryVolsinPG( myArrayTgt, target_protection_group )


    #
    # if the snapshot does not exist create it
    # if safety lock engaged this will return a null string
    #
    if( not source_snap_exists ): snapshot_name=fCreateSnapshot( myArraySrc, args.execute_lock, snapshot_name, source_protection_group, args.replicate )



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
    fQueryVolumesinSnapshot( myArrayTgt, source_protection_group, snapshot_name, lst_source_vols, lst_excluded_vols )



    #
    # if an output file was specified, then write the volume names to it
    #
    if( args.output_file != None ):
        print( '============' )
        lst_excluded_vols = dictArgs.get( "excluded_volumes", [] )
        for vol in lst_excluded_vols: print ( f'excluding:{vol}' )
        mWriteVolumesinSnapshot( args.output_file, lst_excluded_vols )


    #
    # if not target PG was define we stop here
    #
    if target_protection_group==not_defined: mQuit( )



    #
    # query the volumes of the target pg
    # collect these in lst_target_vols
    #
    lst_target_vols = fQueryVolsinPG( myArrayTgt, target_protection_group )


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
    # process the dictSourceVols and then fetch the matching volume from dictTargetVols
    #
    for i in range(20):
    
        my_return = fMapVolumes( myArrayTgt, args.execute_lock )
        if my_return=="": break
        time.sleep(2)


    if my_return!="": 

        print( '============' )
        print( f'ERROR - map did not complete:{my_return}' )

    #
    # end of program
    #
    print( '============' )
    print( 'complete' )


if __name__ == "__main__": doMain()


