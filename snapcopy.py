#!/usr/bin/env python2
import os
import re
import sys
import stat
import errno
import uuid
import getopt
import subprocess
import time
import threading

from utils import Exp, _exec_pipe, _exec_pipe1, _put_remote, _exec_system, _exec_shell, \
        _derror, _isip, _exec_remote, mutil_exec, _human_readable, _human_unreadable
from disk import Disk


def usage():
    print ("usage:")
    print (sys.argv[0] + " --list")
    print (sys.argv[0] + " --backup lun[@snap] {dev|path} [--name] [--keep -k] [--force -f]")
    print (sys.argv[0] + " --restore {dev|path} lun [--name]")
    print (sys.argv[0] + " [--verbose -v] [--help -h]")

class Snapshot:
    def __init__(self, v):
        self.dev = ""
        self.dir = ""
        self.verbose = v
        self.disk = Disk()
        self.defaultpath = "/iscsi/"
        self.lichfs =  "/opt/fusionstack/lich/libexec/lichfs"
        self.lich_snapshot =  "/opt/fusionstack/lich/libexec/lich.snapshot"

    def list_lun(self, v):
        localun = []
        lun = ""
        tgt = ""
        size = ""

        time.sleep(1)
        try:
            res = _exec_pipe([self.lichfs, '--list', self.defaultpath], 0, False)
            for line in res.splitlines():
                pool = line.split(' ')[-1]
                lunres = _exec_pipe([self.lichfs, '--list', self.defaultpath + pool], 0, False)
                for l in lunres.splitlines():
                    lun = l.split(' ')[-1]
                    lunsize = self.getsize(pool+'/'+lun, v)
                    if pool is not None and lun is not None:
                        size = lunsize
                        localun.append((pool + '/' + lun, size))
        except Exp, e:
            _derror('list local lun fail')
            exit(e.errno)
        return localun

    def getsize(self, path, v):
        cmd = [self.lichfs, "--stat", self.defaultpath + path]
        try:
            (out, err) = _exec_pipe1(cmd, 0, v)
            for line in out.splitlines():
                m = re.match("\s+Size:\s+(\d*).*", line)
                if m is not None:
                    return m.group(1)
        except Exp, e:
            if e.err:
                _derror(str(e.err))
                exit(e.errno)

    def list_snap(self, v):
        localsnap = []
        lun = self.list_lun(v)
        for i in lun:
            tgt = self.defaultpath + i[0]
            cmd = [self.lich_snapshot, "--list", tgt]
            try:
                (out, err) = _exec_pipe1(cmd, 0, v)
                for line in out.splitlines():
                    snap = i[0] + "@" + line
                    snapsize = self.getsize(i[0]+'/'+line, v)
                    localsnap.append((i[0], snap, snapsize))
            except Exp, e:
                if e.err:
                    _derror(str(e.err))
                    exit(e.errno)
        return localsnap

    def list(self, v):
        lun = []
        snap = []

        lun = self.list_lun(v)
        snap = self.list_snap(v)
        for i in lun:
            #size = _human_readable(int(i[1]))
            #print ("%s :%s" % (i[0], size))
            print ("%s :%sB" % (i[0], i[1]))
            for j in snap:
                if (i[0] == j[0]):
                    print ("  %s" % (j[1]))

    def is_snap(self, name, v):
        res = 0
        snap = []
        snap = self.list_snap(v)
        for i in snap:
            if (i[1] == name):
                res = 1
        return res

    def is_lun(self, name, v):
        res = 0
        lun = self.list_lun(v)
        for i in lun:
            if (i[0] == name):
                res = 1
        return res

    def is_target(self, name, v):
        res = 0
        tgt = name.split('/')[0]
        lun = self.list_lun(v)
        for i in lun:
            tmptgt = i[0].split('/')[0]
            if (tmptgt == tgt):
                res = 1
        return res

    def mount_dev(self, dev, force = 0):
        self.dev = dev
        try:
            self.dir = "/mnt/snap"
            _exec_system("mkdir -p %s" % self.dir)
        except:
            pass

        if not stat.S_ISBLK(os.lstat(os.path.realpath(self.dev)).st_mode):
            raise Exp('not a block device', dev)

        try:
            (out, err) = _exec_pipe1(["mount", self.dev, self.dir], 0, self.verbose, 0)
        except Exp, e:
            out = e.out
            err = e.err
            for line in err.splitlines():
                m1 = re.search('you must specify the filesystem type', line)
                m2 = re.search('wrong fs type, bad option', line)
                if m1 is not None or m2 is not None:
                    if force:
                        self.disk.dev_format(self.dev, self.verbose)
                        self.disk.dev_mount(self.dev, self.dir, self.verbose)
                    else:
                        _derror('wrong fs type, you must specify the filesystem type or use --force')
                        exit(e.errno)

    def create_snap(self, lun):
        stime = time.strftime('%m%d%H%M')
        snap = self.defaultpath + lun + "@" + stime
        cmd = [self.lich_snapshot, "--create", snap]
        try:
            (out, err) = _exec_pipe1(cmd, 0, self.verbose)
        except Exp, e:
            if e.err:
                _derror(str(e.err))
                exit(e.errno)
        return snap

    def check(self, snapath, path, keep, backuppath):
        snapsize = 0
        devsize = 0

        name = snapath.split('/iscsi/')[1]
        snap = []
        snap = self.list_snap(self.verbose)
        for i in snap:
            if (i[1] == name):
                snapsize = int(i[2])

        st = os.statvfs(path)
        devsize = st.f_bavail * st.f_frsize

        if (snapsize >= devsize):
            self.end(keep, backuppath)
            _derror('snap lun is larger than disk')
            exit(errno.EINVAL)

    def backup(self, lun, path, filename, keep, force, v):
        filepath = ""
        snap = ""
        if (filename == ""):
            name = "snapfile"
        else:
            name = filename

        if path.startswith('/dev/'):
            self.dev = path
            self.mount_dev(path, force)
            filepath = self.dir
        elif os.path.isdir(path):
            filepath = path
        elif path.startswith('/'):
            filepath = os.path.dirname(path)
            if not os.path.exists(filepath):
                try:
                    self.dir = filepath
                    _exec_system("mkdir -p %s" % self.dir)
                except:
                    pass
            #name = os.path.basename(path)
            if path.split('/')[-1] != "":
                name = path.split('/')[-1]
        else:
            self.end(keep, snap)
            _derror('path %s was wrong' % path)
            exit(errno.EINVAL)

        if (self.is_snap(lun, v)):
            snapath = self.defaultpath + lun
        elif (self.is_lun(lun, v)):
            snap = self.create_snap(lun)
            snapath = snap
        else:
            self.end(keep, snap)
            _derror('lun %s was wrong' % lun)
            exit(errno.EINVAL)

        self.check(snapath, filepath, keep, snap)
        cmd = [self.lich_snapshot, '--copy', snapath, ':' + filepath + '/' + name]
        try:
            (out, err) = _exec_pipe1(cmd, 0, self.verbose)
        except Exp, e:
            if e.err:
                self.end(keep, snap)
                _derror(str(e.err).strip())
                exit(e.errno)
        self.end(keep, snap)

    def restore(self, path, lun, filename, v):
        if (path.startswith('/dev/')):
            self.dev = path
            self.mount_dev(path)
            filepath = self.dir + '/' + filename
        else:
            filepath = path + '/' + filename

        if not os.path.exists(filepath):
            self.end()
            _derror( '%s filename is not exist' % (filepath))
            exit(errno.EINVAL)

        if (self.is_target(lun, v) == 1):
            if (self.is_lun(lun, v) == 1):
                self.end()
                _derror( '%s is exist, please rename a new lun' % (lun))
                exit(errno.EINVAL)
        else:
            tgt = os.path.dirname(lun)
            cmd = "lichbd mkpool %s -p iscsi" % (tgt)
            if (self.verbose):
                print cmd
            os.system(cmd)

        cmd = [self.lichfs, "--copy", ":" + filepath, self.defaultpath + lun]
        if (self.verbose):
            print cmd
        try:
            (out, err) = _exec_pipe1(cmd, 0, False)
            print out
        except Exp, e:
            ret = _exec_system("echo $?", False, False)
            if ret and e.err:
                self.end()
                _derror(str(e.err))
                exit(e.errno)
        self.end()


    def end(self, keep = 0, snap = ""):
        try:
            if self.dev != "":
                self.disk.dev_umount(self.dev, self.verbose)
        except:
            pass

        if self.dir != "" and self.dev != "":
            _exec_system("rm -rf %s" % self.dir)

        if keep == 0 and snap != "":
            cmd = [self.lich_snapshot, "--remove", snap]
            try:
                (out, err) = _exec_pipe1(cmd, 0, False)
            except Exp, e:
                if e.err:
                    _derror(str(e.err))
                    exit(e.errno)

def main():
    keep = 0
    force = 0
    verbose = 0
    filename = ""
    lun = ""
    path = ""

    _argv = sys.argv[1:]
    argv = []
    for i in range(len(_argv)):
        if (_argv[i] in ('-k', '--keep')):
            keep = 1
        elif (_argv[i] in ('-v', '--verbose')):
            verbose = 1
        elif (_argv[i] in ('-f', '--force')):
            force = 1
        else:
            argv.append(_argv[i])

    try:
        opts, args = getopt.getopt(
                argv,
                'hv', ['help', 'verbose', 'force', 'keep', 'backup=', 'restore=', 'list']
                )
    except getopt.GetoptError, err:
        print str(err)
        usage()
        exit(errno.EINVAL)

    try:
        snapshot = Snapshot(verbose)
    except Exp, e:
        _derror(e.err)
        exit(e.errno)

    for o, a in opts:
        if o in ('-h', '--help'):
            usage()
            exit(0)
        elif o in '--backup':
            flag = False
            backup_argv = sys.argv
            for i in range(len(backup_argv)):
                if (backup_argv[i] == '--name'):
                    flag = True
                    break

            if flag and (len(sys.argv) <= i + 1):
                _derror('name is null')
                exit(errno.EINVAL)

            if flag and not sys.argv[i+1].startswith('-'):
                filename = sys.argv[i+1]

            if (len(sys.argv) >= 4):
                lun = sys.argv[2].strip()
                path = sys.argv[3].strip()
            else:
                _derror('need lun and path')
                usage()
                exit(errno.EINVAL)
            snapshot.backup(lun, path, filename, keep, force, verbose)
        elif o in '--restore':
            flag = False
            restore_argv = sys.argv
            for i in range(len(restore_argv)):
                if (restore_argv[i] == '--name'):
                    flag = True
                    break

            if flag and (len(sys.argv) <= i + 1):
                _derror('filename is null')
                exit(errno.EINVAL)

            if flag and not sys.argv[i+1].startswith('-'):
                filename = sys.argv[i+1]

            if (len(sys.argv) >= 4):
                path = sys.argv[2].strip()
                lun = sys.argv[3].strip()
            else:
                _derror("need path and lun")
                usage()
                exit(errno.EINVAL)

            if (path.startswith('/dev/') and filename == ""):
                _derror('restore %s need filename' % path)
                exit(errno.EINVAL)

            if not path.startswith('/dev') and flag == False:
                if os.path.isfile(path):
                    filename = os.path.basename(path)
                    path = os.path.dirname(path)
                elif os.path.exists(path):
                    filename = "snapfile"
                else:
                    _derror("path was wrong")
                    exit(errno.EINVAL)
            snapshot.restore(path, lun, filename, verbose)
        elif o in '--list':
            snapshot.list(verbose)
        else:
            usage()
            exit(errno.EINVAL)

if __name__ == '__main__':
    if (len(sys.argv) == 1):
        usage()
    else:
        main()
