#!/usr/bin/env python2
# coding:utf-8

import os
import sys
import time
import fcntl
import types
import errno
import getopt

from node import Node
from disk_manage import DiskManage
from utils import Exp, _dmsg, _dwarn, _derror

class Gbase_disk_manage(DiskManage):
    def __init__(self, gbase = True):
        self.node = Node()
        super(Gbase_disk_manage, self).__init__(self.node)
        self.tier_withtype = gbase

def usage():
    print ("usage:")
    print (sys.argv[0] + " --disk_list [--json]")
    print (sys.argv[0] + " --disk_add dev1 dev2 ...[--force]")
    print (sys.argv[0] + " --disk_del dev1 dev2 ...[--force]")
    print (sys.argv[0] + " --disk_check cache|tier|speed|rotation")
    print (sys.argv[0] + " --set_lun [ssd|hdd]")
    print (sys.argv[0] + " --lun_list [ssd|hdd]")
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
                'hv', ['disk_list', 'disk_add', 'help', 'verbose', 'force', 'json', 'disk_del', 'disk_check=', 'set_lun', 'lun_list']
                )
    except getopt.GetoptError, err:
        print str(err)
        usage()

    for o, a in opts:
        if o in ('--help'):
            usage()
            exit(0)
        elif o == '--json':
            is_json = 1
        elif o == '--force':
            force = Ture
        elif o == '--verbose':
            verbose = 1
        elif o == '--disk_list':
            op = o
        elif (o == '--disk_add'):
            print "args",args
            print 'a',a
            if '--force' in args:
                force = True
            op = o
            ext = args
        elif (o == '--disk_del'):
            if '--force' in args:
                force = True
            op = o
            ext = args
        elif o == '--disk_check':
            op = o
            ext = a
        else:
            assert False, 'oops, unhandled option: %s, -h for help' % o
            exit(1)

    gbase_manage = Gbase_disk_manage(gbase)
    if (op == '--disk_list'):
        gbase_manage.disk_list(is_json)
    elif (op == '--disk_add'):
        print 'add ext',ext
        gbase_manage.disk_add(ext, verbose, force)
    elif (op == '--disk_del'):
        print 'del ext',ext
        gbase_manage.disk_del(ext, verbose)
    elif (op == '--disk_check'):
        if ext not in ['tier']:
            raise Exp(errno.EINVAL, 'disk_check only support tier operate')
        gbase_manage.disk_check(ext)
    else:
        assert False, 'oops, unhandled option: %s, -h for help' % o
        exit(1)

if __name__ == '__main__':
    if (len(sys.argv) == 1):
        usage()
    else:
        main()
