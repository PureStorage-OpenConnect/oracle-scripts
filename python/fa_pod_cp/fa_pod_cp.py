#
# Python script to clone a Flash Array Pod with NFS exported file systems
#
# Graham Thornton - Jan 2025, Nov 2026 (1.3.0)
# gthornton@everpuredata.com
#
# usage:
# python fa_pod_cp.py -s gct-pod-ora-swingdb -t gct-pod-tmp -j json/export_rules.json -a=-clone -x
#


import sys
import os
import datetime
import json
import argparse

import warnings
warnings.filterwarnings(action='ignore')

from pypureclient import flasharray
import urllib3

# disable the HTTPS warnings
urllib3.disable_warnings()

# global variables
HALT=1
NOHALT=0
version = "1.3.0"
not_defined = "Not Defined"

# main dictionary for script variables
dictMain={}

# holds the policy names for the source and target pods
lst_source_policies=[]
lst_target_policies=[]

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

    #print( f'args: {my_flash_array} {my_flash_array_api_token} {my_flash_array_api_version}' )

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
# check that the source pod exists and that the target pod does not
#

def mCheckPodExists( my_array, my_source_pod, my_target_pod ):

    source_found=0

    response = fAPICall( my_array.get_pods, 'call to get_pods failed' )

    #print( response.total_item_count )
    num_pods=0
    for mypod in response.items:
        num_pods += 1
        if( mypod.name == my_source_pod ): source_found=1
        if( mypod.name == my_target_pod ): mError ( HALT, 0, 'target pod '+my_target_pod+' exists, please destroy and eradicate the target, or choose a different target pod name' )
        #  print( mypod )

    if ( source_found==0 ): mError ( HALT, 0, 'source pod '+my_source_pod+' was not found on this Flash Array' )




#
# find the policies on the source pod
# for each policy found, replace the source pod name with the target pod name
# populates the lst_source_policies and lst_target_policies
#

def mQueryPolicies( my_array, my_source_pod, my_target_pod ):

    response = fAPICall( my_array.get_policies_nfs, 'call to get_policies_nfs failed' )

    for policy in response.items:
        # see if this policy is for the source_pod
        #print( policy )
        try:
            pod_policy_name = policy.pod.name
        except:
            pod_policy_name = ''

        if ( pod_policy_name == my_source_pod ):
            print( 'policy '+policy.name )
            lst_source_policies.append( policy.name )
            lst_target_policies.append( policy.name.replace( my_source_pod, my_target_pod ))

    # check this pod actually has policies
    if ( len(lst_source_policies) == 0 ): mError( NOHALT, 0, 'source pod does not appear to have any policies' )

    print( f'number of policies found:{len(lst_source_policies)}' )
    #print( lst_source_policies )
    #print( lst_target_policies )




#
# find the relevant rules for the source pod policies
# we may have to alter the rule to change/limit the client who can access the exported directory
#

def mQueryNFSClientRules( my_array, my_source_pod, my_lst_source_policies ):

    counter=0
    rules=0

    while( counter < len( my_lst_source_policies )):

        mypolicy = my_lst_source_policies[counter];

        print( f'rules for policy:{mypolicy}' )

        try:
            response = my_array.get_policies_nfs_client_rules( policy_names=[mypolicy] )

            for rule in response.items:
            #    print( rule )
                rules+=1

        except:
            print( f'no client rules found for:{mypolicy}' )

        #print( response.items  )

        counter+=1

    print( f'{rules} rule(s) found' )


#
# check that the cloned pod export directories do not already exist
# code will append the export_suffix to each currently exported directory
# and then make sure an export directory that name does not already exist
#

def mQueryCreateExports( my_array, my_export_suffix, my_lst_source_policies ):

    # get the directory exports from the source pod
    response = fAPICall( my_array.get_directory_exports, 'call to get_directory_exports failed', policy_names=my_lst_source_policies )

    # step through the exports
    for my_directory_export in response.items:

        # convert the policy and directory names by replacing the source pod name with the target pod name
        target_export_name = my_directory_export.export_name+my_export_suffix

        # check to see if this export already exists - it should not
        # we should get a 400 status on this call
        try:
            response2 = my_array.get_directory_exports( export_names=[target_export_name] )
        except Exception as e:
            mError( HALT, 0, f'get_directory_exports call returned an error: {e}' )

        # if we got a 200 code the export already exists under a different pod
        if( response2.status_code==200 ):

            print( f'cannot create target export directory:{target_export_name}' )

            # step through the matching records we got back to see which pods this export directory already exists in
            for my_directory_export_exists in response2.items:

                print( f'directory already exists for policy:{my_directory_export_exists.policy.name}' )
                print( f'directory already for directory:{my_directory_export_exists.directory.name}' )
                #print( my_directory_export_exists )

            #print( response.status_code )
            mError ( HALT, response2.status_code, 'select an alternative export suffix' )




#
# list the file systems for the source pod
# file systems have the naming convention POD::FILESYSTEM
# this is informational only - the pod clone copies the file systems itself
#

def mQueryFileSystems( my_array, my_source_pod ):

    num_file_systems=0

    response = fAPICall( my_array.get_file_systems, 'call to get_file_systems failed' )
    if response is None: return

    # step through the list of file systems returned
    for file_system in response.items:

        # try to see if this file system has a pod, some do not
        try:
            pod_name = file_system.pod.name

            # this file system is part of a pod, check if it is the source_pod
            if( pod_name == my_source_pod ):

                print( f'file system {file_system.name}' )
                num_file_systems+=1

        except:
            pod_name = ''
            #print( 'not part of a pod' )

    # check this pod actually has some file systems
    if ( num_file_systems == 0 ): mError( NOHALT, 0, 'source pod does not appear to have any NFS file systems' )

    print( f'number of source pod file systems found:{num_file_systems}' )




#
# clone the pod
#

def mClonePod( my_array, my_source_pod, my_target_pod ):

    mypod={
     'name': my_target_pod ,
     'quota_limit': 0,
     'requested_promotion_state': 'promoted',
     'source': {'name': my_source_pod },
    }

    response = fAPICall( my_array.post_pods, 'call to post_pods failed', names=[my_target_pod], pod=mypod )

    # fAPICall halts on a non-200 response, but returns None if the call raised
    if response is None: mQuit( f'pod {my_target_pod} was not created - cannot continue' )


#
# replace the original export rules with the ones specified in the JSON file
# if it was given
#

def mChangeExportRules( my_array, safe_mode, my_rules, my_lst_target_policies ):

    # see if new export rules were specified
    export_rules = dictMain.get( "rules", None )

    if( export_rules is None ):
        print( f'no export rules were defined, rules were copied from the source policy' )
        return

    #print( f'{export_rules}' )


    for policy in my_lst_target_policies:

        if( safe_mode ):
            print( f'NOTE: would replace client rules on {policy} with {len(export_rules)} rule(s)' )
            continue

        response = fAPICall( my_array.get_policies_nfs_client_rules, 'call to get_policies_nfs_client_rules failed', policy_names=[policy] )
        if response is None: mQuit( f'could not read rules for {policy} - cannot continue' )

        for rule in response.items:
            print( f'deleting rule {rule.name}' )
            r = fAPICall( my_array.delete_policies_nfs_client_rules,
                    'call to delete_policies_nfs_client_rules failed',
                    policy_names=[policy], names=[rule.name] )
            if r is None: mQuit( f'could not delete rule {rule.name} - cannot continue' )

        r = fAPICall( my_array.post_policies_nfs_client_rules,
                'call to post_policies_nfs_client_rules failed',
                policy_names=[policy], rules={'rules': export_rules} )
        if r is None: mQuit( f'could not add rules to {policy} - cannot continue' )

        print( f'replaced client rules on {policy}' )

#
# apply directory exports to the cloned pod
# we gather the exports for the source systems and then
# replace the source pod name with the target pod name
# a suffix is added to the export names
#

def mApplyDirectoryExports( my_array, safe_mode, my_source_pod, my_target_pod, my_export_suffix, my_lst_source_policies ):

    print( f'getting directory exports for {my_source_pod}' )

    response = fAPICall(
            my_array.get_directory_exports,
            'call to get_directory_exports failed',
            policy_names=my_lst_source_policies
    )
    if response is None: return

    # step through the exports
    for my_directory_export in response.items:

        # convert the policy and directory names by replacing the source pod name with the target pod name
        target_export_name = my_directory_export.export_name+my_export_suffix
        target_directory_name = my_directory_export.directory.name.replace( my_source_pod, my_target_pod )
        target_policy_name = my_directory_export.policy.name.replace( my_source_pod, my_target_pod )

        # create the export name
        myexport={
            'export_name': target_export_name,
            'path': '/',
        }

        # check for safety lock
        if( safe_mode ):

            print( f'NOTE: clone of {my_directory_export.export_name} would be exported as {target_export_name}' )

        else:

            # try to add the export
            response2 = fAPICall(
                    my_array.post_directory_exports,
                    'call to post_directory_exports failed',
                    directory_names=[ target_directory_name ], exports=myexport, policy_names=[ target_policy_name ]
            )

            if response2 is None:
                mError( NOHALT, 0, f'clone of {my_directory_export.export_name} was NOT exported as {target_export_name}' )
            else:
                print( f'clone of {my_directory_export.export_name} exported as {target_export_name}' )





##############################################

# MAIN BLOCK

##############################################

def doMain( ):

    print( '============' )
    print( f'fa_pod_cp.py {version} started at {datetime.datetime.now()}' )

    # parse the command line args
    parser = argparse.ArgumentParser(
                    prog='fa_pod_cp ', usage='%(prog)s [ options ]',
                    description='clone a pod of NFS file system(s) on an Everpure Flash Array',
                    epilog='coded by Graham Thornton - gthornton@everpuredata.com')

    parser.add_argument('-s','--source_pod', help='name of the source pod', required=True)
    parser.add_argument('-t','--target_pod', help='name of target pod to be created', required=True)
    parser.add_argument('-a','--append_suffix', help='suffix to append to cloned file system exports' )
    parser.add_argument('-j','--config_file', help='json document of config options', required=False)
    parser.add_argument('-x','--execute_lock', action='store_false', help="specify -x to actually clone the pod (default is safety lock on)")

    args = parser.parse_args()

    #
    # read the config file
    #
    global dictMain;
    if( args.config_file != None ): dictMain = fReadConnectionJSON( args.config_file )

    # fa variables
    flash_array = dictMain.get( "src_flash_array_host", dictMain.get( "flash_array_host", os.environ.get('PUREFA_URL')))
    flash_array_api_token = dictMain.get( "src_flash_array_api_token", dictMain.get( "flash_array_api_token", os.environ.get('PUREFA_API')))
    flash_array_api_version = dictMain.get( "flash_array_api_version" )

    if( flash_array==None or flash_array_api_token==None ):
        mQuit( 'flash_array_host and flash_array_api_token need to be defined in the config file or environment variables' )

    #
    # connect to the FA
    #
    myArray = fFAConnect( flash_array, flash_array_api_token, flash_array_api_version )


    print( '============' )
    print( f'cloning pod {args.source_pod} to {args.target_pod}' )


    # check source pod exists and target pod does not
    print( '============' )
    print( 'checking for existence of source-pod and non-existence of target-pod' )

    mCheckPodExists( myArray, args.source_pod, args.target_pod )



    # read the NFS policies of the source pod
    print( '============' )
    print( f'determining relevant policies for {args.source_pod}' )

    mQueryPolicies( myArray, args.source_pod, args.target_pod )



    # read the NFS client rules for the source pod
    print( '============' )
    print( f'determining client rules for NFS policies for {args.source_pod}' )

    mQueryNFSClientRules( myArray, args.source_pod, lst_source_policies )



    # check we can create the export directories
    if args.append_suffix is not None:

        print( '============' )
        print( 'checking that target export directories can be created' )

        mQueryCreateExports( myArray, args.append_suffix, lst_source_policies )



    # read the source file systems
    print( '============' )
    print( f'determining file systems for {args.source_pod}' )

    mQueryFileSystems( myArray, args.source_pod )



    # clone the pod
    print( '============' )
    print( f'cloning pod {args.source_pod} to {args.target_pod}' )

    # only do this if safety lock disabled
    if ( args.execute_lock ):

        print( 'NOTE: safety lock is engaged, so no actual pod clone will be executed' )
        print( 'NOTE: to disable add -x to arguments' )

    else:

        # clone the pod
        mClonePod( myArray, args.source_pod, args.target_pod )



    #
    # apply the policies to the cloned pod
    # despite the documentation, this has to be done one at a time.
    #

    print( '============' )
    print( f'cloning policies for {args.target_pod}' )

    policy=0
    while( policy < len( lst_source_policies )):

        # check for safety lock
        if( args.execute_lock ):

            print( f'NOTE: would clone policy {lst_source_policies[policy]} as {lst_target_policies[policy]}' )

        else:

            print( f'cloning policy {lst_source_policies[policy]} as {lst_target_policies[policy]}' )

            response = fAPICall(
                    myArray.post_policies_nfs,
                    'call to post_policies_nfs failed',
                    names=[lst_target_policies[policy]], source_names=[lst_source_policies[policy]]
            )

            # fAPICall halts on a non-200 response, but returns None if the call raised
            if response is None: mQuit( f'policy {lst_target_policies[policy]} was not created - cannot continue' )

        policy+=1


    print( '============' )

    mChangeExportRules( myArray, args.execute_lock, args.config_file, lst_target_policies )

    #
    # apply directory exports to the cloned pod
    # we gather the exports for the source systems and then
    # replace the source pod name with the target pod name
    # a suffix is added to the export names
    #

    print( '============' )

    if args.append_suffix is not None:

        mApplyDirectoryExports( myArray, args.execute_lock, args.source_pod, args.target_pod, args.append_suffix, lst_source_policies )

    else:

        print( 'no export suffix specified so cloned file systems will not be exported' )



    print( '============' )
    print( 'pod cloning complete' )


if __name__ == "__main__": doMain()
