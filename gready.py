#!/usr/bin/env python2
# coding:utf-8

import os
import re
import sys
import time
import fcntl
import types
import errno
import getopt

from node import Node
from config import Config
from disk_manage import DiskManage
from utils import Exp, _dmsg, _dwarn, _derror, _exec_shell, _exec_pipe, \
    mutil_exec, _exec_pipe1, _human_readable, _exec_system, _str2dict

class Gbase_lich_ready():
    def __init__(self, config):
        self.lichfs =  config.lichexec
        self.success = 0
        self.fail = 0
        self.fail_lun = []

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

    def getstat(self, path):
        cmd = [self.lichfs, "--stat", path]
        try:
            (out, err) = _exec_pipe1(cmd, 0, False)
            ret = _exec_system("echo $?", False, False)
            if ret == 0:
                self.success += 1
                #_dmsg('check %s successful' % (path))
            else:
                self.fail += 1
                self.fail_lun.append(path)
        except Exp, e:
            self.fail += 1
            self.fail_lun.append(path)
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
            lun_info.append((l,size))

        return lun_info

    def check_lun(self):
        lun_info = []
        lun_info = self._lun_list()

        if len(lun_info):
            lun = [l[0] for l in lun_info]
        else:
            _dmsg('There is no lun ')
            exit(0)

        for l in lun:
            res = self.getstat(l)

        _dmsg('success lun : %d' % (self.success))
        _dmsg('fail lun : %d' % (self.fail))

        fail_lun = list(set(self.fail_lun))
        if len(fail_lun):
            _dmsg('fail lun : ')
            for l in fail_lun:
                _dmsg('\t%s' % l)
        else:
            _dmsg('the cluster is ready. ')

def main():
    config = Config()
    gready = Gbase_lich_ready(config)
    gready.check_lun()

if __name__ == '__main__':
    main()
