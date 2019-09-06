#!/bin/python3

import argparse
import subprocess
import sys
import os
import re
from pathlib import Path

class NoSuchConfig(Exception):
    pass

class InvalidRemote(Exception):
    pass

class Remote():

    server = ""
    path = Path()
    port = None
    idPath = None

    def __init__(self, s, port=None, idPath=None):
        r = re.compile(r'(?:(?P<server>(?:\w+@)?.+):)?(?P<path>.+)')
        match = r.match(s)
        if not match:
            raise InvalidRemote('Invalid remote string: ' + s)
        else:
            match = match.groupdict()
            if "server" in match:
                self.server = match["server"]
            else:
                self.server = ""
            self.path = Path(match["path"])
        self.port = port
        self.idPath = idPath
        
        sshString = []
        self.sshCommand = []
        if port:
            print("PORT")
            sshString.append('"/usr/bin/ssh')
            sshString.append('-p ' + str(port))
            if not idPath:
                sshString[1] += '"'
        if idPath:
            if not port:
                sshString.append('"ssh')
            sshString.append('-i ' + str(Path(idPath).expanduser().resolve()) + '"')
        sshString = " ".join(sshString)
        if sshString:
            self.sshCommand = ['-e', sshString]
        print(self.sshCommand)


    def __truediv__(self, path):
        newRemote = Remote(str(self), self.port, self.idPath)
        newRemote.path /= path
        return newRemote

    def __str__(self):
        if self.server:
            return self.server + ":" + str(self.path)
        else:
            return str(self.path)
        

def sync(direction, remote, bl, wl, force, port, pk, config):

    def runCommand(args, output=True):
        result = subprocess.run(args, capture_output=output)
        if result.returncode:
            raise Exception()
        if output:
            print(result.stdout)
            

    def diff(path1, path2):
        command = ['diff', '-y', '--color=always', str(path2), str(path1)]
        try:
            runCommand(command, False)
        except:
            pass

    def ask(src, dst):
        a = ""
        while a.lower() not in ['y', 'n', 'd']:
            a = input("Overwrite " + str(dst) + "?  Use d for diff (y/n/d):")
        if a == "y":
            return True
        if a == "n":
            return False
        if a == "d":
            diff(src, dst)
        return ask(src, dst)

    def resolvePath(filename):
        return str(Path(filename).expanduser().resolve())

    def buildRsyncCommand(srcPath, dstPath, baseCommand):
        command = baseCommand.copy()
        command.extend(remote.sshCommand)
        if type(srcPath) is list:
            command.extend(srcPath)
        else:
            command.append(str(srcPath))
        command.append(str(dstPath))
        print(command)
        return command

    def clearTemp(confDict):
        t = Path("/tmp")
        for f in confDict:
            p = t/f
            if p.is_file():
                os.remove(p)

    def rsyncFrom(rsyncList, baseDir, configDict):
        [runCommand(buildRsyncCommand(str(baseDir / p), configDict[p], ['rsync', '-b'] + remote.sshCommand), False) for p in rsyncList]

    #copies the local files to a new location, and renames them to their 
    #remote names
    def syncAndRename(rsyncList, configDict, dst, baseCommand):
        command = baseCommand.copy()
        for r in rsyncList:
            command.extend([configDict[r], dst / r])
            runCommand(command, False)
            command = baseCommand

    def push(rsyncList, configDict, baseCommand):
        c = rsyncList.copy()
        if remote.server:
            #stage the files in the /tmp directory 
            syncAndRename(c, configDict, Path("/tmp"), ['rsync'])
            c = [str(Path("/tmp") / p) for p in c]
            command = buildRsyncCommand(c, str(remote / '.'), baseCommand.copy())
            runCommand(command, False)
        else:
            [runCommand(buildRsyncCommand(configDict[p], str(remote / p), baseCommand.copy()), False) for p in rsyncList]

    def getLocalCopy(rsyncList):
        remoteList = []
        for f in rsyncList:
            remoteList.append(str(remote / f))
        command = buildRsyncCommand(remoteList, '/tmp/', ['rsync'] + remote.sshCommand)
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

    def askOverwrite(compareSrc, compareDst, rsyncList):
        i = 0
        while i < len(rsyncList):
            if compareDst[i].is_file():
                if subprocess.run(['cmp', '-s', compareSrc[i], compareDst[i]]).returncode:
                    if not ask(compareSrc[i], compareDst[i]):
                        compareSrc.pop(i)
                        compareDst.pop(i)
                        rsyncList.pop(i)
                else:
                    compareSrc.pop(i)
                    compareDst.pop(i)
                    rsyncList.pop(i)

            i += 1


    configPath=resolvePath(config)
    configDictionary=dict(line.strip().split(':', 1) for line in open(configPath))
    for k in configDictionary:
        configDictionary[k] = Path(configDictionary[k]).expanduser().resolve()
    rsyncList = getRsyncList(configDictionary)
    push(rsyncList, configDictionary, ['rsync', '--ignore-existing'] + remote.sshCommand)
    compareSrc = []
    compareDst = []
    if remote.server:
        getLocalCopy(rsyncList) 
        p = Path("/tmp")
        if direction == "to":
            for name in rsyncList:
                compareDst.append(p / name)
                compareSrc.append(configDictionary[name])
        else:
            for name in rsyncList:  
                compareDst.append(configDictionary[name])
                compareSrc.append(p / name)
    else:
        if direction == "to":
            for name in rsyncList:
                compareDst.append(remote.path / name)
                compareSrc.append(configDictionary[name])
        else:
            for name in rsyncList:
                compareDst.append(configDictionary[name])
                compareSrc.append(remote.path / name)

    askOverwrite(compareSrc, compareDst, rsyncList)
    if direction == "to":
        push(rsyncList, configDictionary, ['rsync', '-b'] + remote.sshCommand)
    else:
        baseDir = ""
        if remote.server:
            baseDir = Path("/tmp")
        else:
            baseDir = remote.path
        rsyncFrom(rsyncList, baseDir, configDictionary)

    clearTemp(configDictionary)
    

if __name__ == "__main__":

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
        sync(args['direction'], Remote(args['remote'], args['port'], args['identity_file']), args['blacklist'],                 \
                args['whitelist'], args['force'], args['port'],                    \
                args['identity_file'], args['config'])
    except TypeError:
        if len(sys.argv) == 1:
            parser.print_usage()
            sys.exit(0)
        else:
            print("Unexpected TypeError", file=sys.stderr)
            raise
