#!/bin/python3

import argparse
import subprocess
import sys
import os
from pathlib import Path

class NoSuchConfig(Exception):
    pass

def sync(direction, remote, bl, wl, force, port, pk, config):

    def runCommand(args, output=True):
        result = subprocess.run(args, capture_output=output)
        if result.returncode:
            raise Exception()
        if output:
            print(result.stdout)
            

    def diff(path1, path2):
        command = ['diff', '-y', '--color=always', str(path1), str(path2), '|', 'less', '-r']
        runcommand(command, False)

    def ask(localPath, tmpPath):
        a = ""
        while a.to_lower() not in ['y', 'n', 'd']:
            if direction == "to":
                a = input("Overwrite remote version of " + str(localPath) + \
                        "? Use d to show diff (y/n/d): ")
            else:
                a = input("Overwrite " + str(localPath) + "? Use d to show diff\
                    (y/n/d): ")
        if a == "y":
            return True
        if a == "n":
            return False
        if a == "d":
            if direction == "to":
                diff(tmpPath, localPath)
            else:
                diff(localPath, tmpPath)
        return ask(localPath, tmpPath)

    def resolvePath(filename):
        return str(Path(filename).expanduser().resolve())

    def buildRsyncCommand(srcPath, dstPath):
        command = ['rsync']
        if pk:
            command.append('-e')
            command.append('"ssh -i ' + pk + '"')
        if type(srcPath) is list:
            command += srcPath
        else:
            command.append(str(srcPath))
        command.append(str(dstPath))
        print(command)
        return command

    def syncFile(localPath, remoteName):
        command = ""
        if direction == "to":
            command = buildRsyncCommand(localPath, remote + '/' + remoteName)
        else:
            command = buildRsyncCommand('/tmp/' + remoteName, localPath)
        if not force and ((direction == "to" and os.path.isfile('/tmp/remoteName') or (direction == "from" and os.path.isfile(localPath)))):
            if ask(localPath, '/tmp/' + remoteName):
                runCommand(command)
        else:
            runCommand(command)

    def syncFiles(fileList, confDict):
        for f in fileList:
            syncFile(confDict[f].strip(), f)

    def pushNew(rsyncList, configDict):
        copyList = []
        for f in rsyncList:
            copyList.append(resolvePath(configDict[f].strip()))
        print(copyList)
        command = ['rsync', '--ignore-existing']
        for f,r in zip(copyList, rsyncList):
            command.append(f)
            command.append(remote + '/' + r)
            print(command)
            runCommand(command, False)
            command = ['rsync', '--ignore-existing']

    def getLocalCopy(rsyncList):
        remoteList = []
        for f in rsyncList:
            remoteList.append(remote + "/" + f)
        command = buildRsyncCommand(remoteList, '/tmp/')
        runCommand(command, False)
        
    def syncWL(confDict):
        l = []
        for key in wl:
            if key in confDict:
                l.append(key)
        return l

    def syncBL(confDict):
        l = []
        for key in confDict:
            if key not in bl:
                l.append(key)
        return l

    def normalSync(confDict):
        l = []
        for key in confDict:
            l.append(key)
        return l

    def getRsyncList(confDict):
        if wl != None:
            return syncWL(confDict)
        elif bl != None:
            return syncBL(confDict)
        else:
            return normalSync(confDict)

    configPath=resolvePath(config)
    configDictionary=dict(line.split(':', 1) for line in open(configPath))
    rsyncList = getRsyncList(configDictionary)
    pushNew(rsyncList, configDictionary)
    print(rsyncList)
    getLocalCopy(rsyncList)
    syncFiles(rsyncList, configDictionary)
    

#program description
description='Copies configs to/from locations defined in the config'

#command help
excludeHelp='Copy all configs but the ones provided by this argument.'
includeHelp='Copy only these configs.'
forceHelp='Force copy without asking or showing diff.'
remoteHelp='Location to copy configs to/from. This can be anywhere reachable\
        by rsync'
portHelp='Set port to access remote location by.'
idHelp='Set ID file for remote location.'
configHelp='Config file.'

parser = argparse.ArgumentParser(description=description)

#blacklist and whitelist are mutually exclusive
blwlgroup = parser.add_mutually_exclusive_group()

parser.add_argument('direction', choices=['to', 'from'])
parser.add_argument('remote', help=remoteHelp)
blwlgroup.add_argument('-b', '--blacklist', nargs='+', help=excludeHelp)
blwlgroup.add_argument('-w', '--whitelist', nargs='+', help=includeHelp)
parser.add_argument('-f', '--force', action='store_true', help=forceHelp)
parser.add_argument('-p', '--port', type=int, help=portHelp)
parser.add_argument('-i', '--identity-file', help=idHelp)
parser.add_argument('-c', '--config', type=str, default='config', help=configHelp)

args = {}

try:
    args = vars(parser.parse_args(sys.argv[1:]))
    print(args)
    sync(args['direction'], args['remote'], args['blacklist'],                 \
            args['whitelist'], args['force'], args['port'],                    \
            args['identity_file'], args['config'])
except TypeError:
    if len(sys.argv) == 1:
        parser.print_usage()
        sys.exit(0)
    else:
        print("Unexpected TypeError", file=sys.stderr)
        raise
