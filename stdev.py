#!/usr/bin/env python2

import errno
import os
import sys
import time
import types
import errno
import getopt
import math

from color_output import red, yellow, blue, green, darkgreen
from utils import Exp, _dmsg, _dwarn, _derror, _str2dict, _getrack, _exec_pipe, _human_unreadable, _human_readable

class StandDeviation:
    def __init__(self):
        self.lich_admin = "/opt/mds/lich/libexec/lich.admin"

    def __get_used_percent(self, lst = None):
        #lst = ['node4/0', 'node4/1', 'node4/2', 'node4/3', 'node5/0']
        used_percent = []

        res = _exec_pipe([self.lich_admin, '--listnode'], 3, False)[:-1]
        if lst:
            list = [x.strip() for x in res.splitlines() if x.strip() in lst]
        else:
            list = [x.strip() for x in res.splitlines()]

        if len(list) == 0:
            _derror("node is not exists")
            exit(errno.EINVAL)

        for node in list:
            res = _exec_pipe([self.lich_admin, '--stat', node], 3, False)[:-1]
            if (len(res) != 0):
                d = _str2dict(res)
                used = d['used']
                capacity = d['capacity']
                percent = float(used) / float(capacity) * 100
                used_percent.append((node, percent, used, capacity))
        return sorted(used_percent, key=lambda d:d[1], reverse=False)

    def get_used_percent(self, lst = None):
        percent = self.__get_used_percent(lst)
        for i in percent:
            _dmsg("%s used %2.0f%% capacity %s" % (i[0], i[1], _human_readable(int(i[3]))))

    def get_used_stand(self, lst):
        percent = self.__get_used_percent(lst)
        aver = sum([float(x[1]) for x in percent]) / len(percent)

        list = [(float(x[1]) - aver) for x in percent]
        total = sum([float(i) * float(i) for i in list])

        stdev = math.sqrt(total / len(percent))
        _dmsg("aver %2.0f%% stdev %f" % (aver, stdev))
        return (aver, stdev)

    def get_capacity_stand(self):
        percent = self.__get_used_percent()
        percent = sorted(percent, key=lambda d:d[3], reverse=False)
        aver = sum([float(x[3]) for x in percent]) / len(percent)

        list = [(float(x[3]) - aver) for x in percent]
        total = sum([float(i) * float(i) for i in list])
        stdev = math.sqrt(total / len(percent))
 
        _dmsg("aver %s stdev %f" % (_human_readable(int(aver)), stdev))
        return (aver, stdev)

def usage():
    print ("standard deviation usage:")
    print (sys.argv[0] + " --used_percent [nodeX/X nodeX/X...]")
    print (sys.argv[0] + " --used_stdev [nodeX/X nodeX/X...]")
    print (sys.argv[0] + " --capacity_stdev")

def main():
    try:
        opts, args = getopt.getopt(
                sys.argv[1:], 
                'h', ['used_percent', 'used_stdev', 'capacity_stdev', 'help']
                )
    except getopt.GetoptError, err:
        print str(err)
        usage()

    if (len(sys.argv) == 1):
        usage()
        exit(0)

    stand = StandDeviation()
    for o, a in opts:
        if o in ('--help'):
            usage()
            exit(0)
        elif o == '--used_percent':
            stand.get_used_percent(args)
        elif o == '--used_stdev':
            stand.get_used_stand(args)
        elif o == '--capacity_stdev':
            stand.get_capacity_stand()
        else:
            assert False, 'oops, unhandled option: %s, -h for help' % o
            exit(1)

if __name__ == '__main__':
    main()
