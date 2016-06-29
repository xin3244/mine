#!/usr/bin/env python2
# coding:utf-8

import os
import re
import sys
import time
import copy
import fcntl
import types
import errno
import getopt

from node import Node
from disk_manage import DiskManage
from utils import Exp, _dmsg, _dwarn, _derror, _exec_shell, _exec_pipe, \
    mutil_exec, _exec_pipe1, _human_readable, _exec_system, _str2dict

class Gbase_disk_manage(DiskManage):
    def __init__(self, gbase = True):
        self.node = Node()
        super(Gbase_disk_manage, self).__init__(self.node)
        self.tier_withtype = gbase
        self.lichfs =  self.config.lichexec
        self.chunksize = 1024 * 1024

    def is_dir(self, path):
        cmd = [self.lichfs, "--stat", path]
        try:
            (out, err) = _exec_pipe1(cmd, 0, False)
            for line in out.splitlines():
                m = re.match(".*Id:\s+(pool).*", line)
                if m is not None:
                    return True 
        except Exp, e:
            if e.err:
                _derror(str(e.err))
                exit(e.errno)
        return False

    def gettier(self, path):
        #replica : 1908
        #allocated : 0
        #tier0 : 0
        #tier1 : 0

        tier_info = []
        cmd = [self.config.inspect, "--tier", path]
        try:
            (out, err) = _exec_pipe1(cmd, 0, False)
            for line in out.splitlines():
                m1 = re.match("\s*tier0 :\s+(\d*).*", line)
                if m1 is not None:
                    ssd = m1.group(1)
                m2 = re.match("\s*tier1 :\s+(\d*).*", line)
                if m2 is not None:
                    hdd = m2.group(1)
            tier_info.append((ssd, hdd))
        except Exp, e:
            if e.err:
                _derror(str(e.err))
                exit(e.errno)

        return tier_info

    def getsize(self, path):
        cmd = [self.lichfs, "--stat", path]
        try:
            (out, err) = _exec_pipe1(cmd, 0, False)
            for line in out.splitlines():
                m = re.match("\s+Size:\s+(\d*).*", line)
                if m is not None:
                    return m.group(1)
        except Exp, e:
            if e.err:
                _derror(str(e.err))
                exit(e.errno)
        return None

    def getallocated(self, path):
        cmd = [self.config.inspect, "--stat", path]
        try:
            (out, err) = _exec_pipe1(cmd, 0, False)
            for line in out.splitlines():
                m = re.match("\s*allocated :\s+(\d*).*", line)
                if m is not None:
                    return m.group(1)
        except Exp, e:
            if e.err:
                _derror(str(e.err))
                exit(e.errno)

        return None

    def _lun_list(self):
        lun = []
        lun_info = []
        pool = []
        tgt = []

        dir = '/'
        res = _exec_pipe([self.lichfs, '--list', dir], 0, False)
        for r in res.splitlines():
            r = dir + r.split(' ')[-1]
            if r == '/system':
                continue
            res = _exec_pipe([self.lichfs, '--list', r], 0, False)
            for p in res.splitlines():
                p = p.split(' ')[-1]
                pool.append(r + dir + p)

        for p in pool:
            res = _exec_pipe([self.lichfs, '--list', p], 0, False)
            for l in res.splitlines():
                l = l.split(' ')[-1]
                path = p + dir + l
                if self.is_dir(path):
                    tgt.append(path)
                else:
                    lun.append(path)

        for t in tgt:
            res = _exec_pipe([self.lichfs, '--list', t], 0, False)
            res = [x.split(' ')[-1] for x in res.splitlines()]
            for l in res:
                path = t + dir + l
                if(self.is_dir(path)):
                    _dmsg('%s is dir' % path)
                    _derror('list lun fail')
                    #exit(e.errno)
                else:
                    lun.append(path)
    
        for l in lun:
            size = self.getsize(l)
            size = _human_readable(int(size))
            allocated = self.getallocated(l)
            allocated = _human_readable(int(allocated) * self.chunksize)
            lun_info.append((l, size, allocated))

        return lun_info

    def lun_list(self, ext=None):
        lun_info = []
        lun_list = []

        #time.sleep(1)
        lun_info = self._lun_list()

        for l,size,a in lun_info:
            tier = self.gettier(l)
            lun_list.append((l, size, a, tier))

        for l in lun_list:
            for t in l[3]:
                ssd = int(t[0])
                hdd = int(t[1])
            if ext == 'ssd' and ssd > 0:
                print ("%s \t%s \t%s \t(ssd :%s)" % (l[0], l[1], l[2], ssd))
            elif ext == 'hdd' and hdd > 0:
                print ("%s \t%s \t%s \t(hdd :%s)" % (l[0], l[1], l[2], hdd))
            elif ext is None:
                print ("%s \t%s \t%s \t(ssd :%s, hdd :%s)" % (l[0], l[1], l[2], ssd, hdd))
        return lun_list

    def set_lun(self, path, ext):
        if ext == 'ssd':
            num = 0
        elif ext == 'hdd':
            num = 1

        cmd = [self.config.inspect, "--tier", path, str(num)]
        try:
            (out, err) = _exec_pipe1(cmd, 0, False)
            ret = _exec_system("echo $?", False, False)
            if ret == 0:
                _dmsg('set %s %s successful' % (path, ext))
        except Exp, e:
            if e.err:
                _derror(str(e.err))
                exit(e.errno)

def usage():
    print ("usage:")
    print (sys.argv[0] + " --disk\t<list|add|del> [dev1 dev2 ...] [--json|-j][--force|-f][--verbose|-v]")
    print (sys.argv[0] + " --tier\t<list>")
    print (sys.argv[0] + " --lun\t<list|set> [lun path] [hdd|ssd]")
    exit(1)

def main():
    op = ''
    ext = None
    verbose = 0
    is_json = 0
    gbase = True
    force = False

    try:
        opts, args = getopt.getopt(
                sys.argv[1:], 
                'hvjf', ['disk=', 'tier=', 'help', 'verbose', 'force', 'json', 'lun=']
                )
    except getopt.GetoptError, err:
        print str(err)
        usage()

    newopts = copy.copy(opts)
    for o, a in opts:
        if o in ('-v', '--verbose'):
            verbose = 1
            newopts.remove((o, a))
        elif o in ('-j', '--json'):
            is_json = 1
            newopts.remove((o, a))
        elif o in ('-f', '--force'):
            force = True
            newopts.remove((o, a))

    newargs = copy.copy(args)
    for o in args:
        if o in ('-v', '--verbose'):
            verbose = 1
            newargs.remove(o)
        elif o in ('-j', '--json'):
            is_json = 1
            newargs.remove(o)
        elif o in ('-f', '--force'):
            force = True
            newargs.remove(o)

    for o, a in newopts:
        if o in ('--help'):
            usage()
            exit(0)
        elif o == '--disk':
            if a not in ['list', 'add', 'del']:
                _derror('disk  only support list add del operate')
                exit(errno.EINVAL)
            if a in ['add', 'del'] and len(newargs) == 0:
                _derror('add/del need dev')
                exit(errno.EINVAL)
            op = o
            type = a
            ext = newargs
        elif o == '--tier':
            op = o
            type = a
            ext = newargs
        elif o == '--lun':
            op = o
            type = a
            ext = newargs
            if a not in ['list', 'set']:
                _derror('lun only support list set operate')
                exit(errno.EINVAL)
        else:
            assert False, 'oops, unhandled option: %s, -h for help' % o
            exit(1)

    gbase_manage = Gbase_disk_manage(gbase)
    if (op == '--disk'):
        if (type == 'list'):
            gbase_manage.disk_list(is_json)
        elif (type == 'add'):
            gbase_manage.disk_add(ext, verbose, force)
        elif (type == 'del'):
            gbase_manage.disk_del(ext, verbose)
    elif (op == '--tier'):
        if type =='list':
            type = 'tier'
        else:
            _derror('tier only support list operate')
            exit(errno.EINVAL)
        gbase_manage.disk_check(type)
    elif (op == '--lun'):
        if (type == 'list'):
            if len(ext) == 0:
                gbase_manage.lun_list()
            elif len(ext) == 1 and ext[0] in ['ssd', 'hdd']:
                gbase_manage.lun_list(ext[0])
            else:
                _derror('lun list support ssd hdd')
                exit(errno.EINVAL)
        elif (type == 'set'):
            if len(ext) != 2:
                _derror('set tier need path and set num')
                exit(errno.EINVAL)
            path = ext[0]
            num = ext[1]
            if ext[1] not in ['ssd', 'hdd']:
                _derror('set lun only support ssd hdd operate')
                exit(errno.EINVAL)
            gbase_manage.set_lun(path, num)
    else:
        assert False, 'oops, unhandled option: %s, -h for help' % o
        exit(1)

if __name__ == '__main__':
    if (len(sys.argv) == 1):
        usage()
    else:
        main()
