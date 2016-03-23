#!/usr/bin/env python2
import os
import re
import sys
import errno
import uuid
import getopt
import commands
import subprocess
import time

def usage():
    print ("usage:")
    print (" step 1: " + sys.argv[0] + " --down")
    print (" step 2: " + sys.argv[0] + " --install")
    print (" help :  " + sys.argv[0] + " [--verbose -v] [--help -h]")

def check_etc_resolv():
    dns = []
    dns.append('nameserver 8.8.8.8\n')
    dns.append('nameserver 8.8.4.4\n')
    for m in dns:
	cmd = "grep '" + m + "' /etc/resolv.conf";
 	res = os.popen(cmd).read()
	if res == "":
 	    fd = open('/etc/resolv.conf', 'a')
	    fd.write(m)
	    fd.close

def check_unzip():
    args = [ 'which', 'unzip', ]
    process = subprocess.Popen(
        args=args,
        stdout=subprocess.PIPE,
        )
    unzip_path, _ = process.communicate()
    ret = process.wait()
    if ret != 0:
        print ('unzip installed. Ubuntu:apt-get install unzip, CentOS:yum install unzip')
	(distro, release, codename) = lsb_release()
        if distro == 'CentOS':
            os.system("yum -y install unzip")
        elif distro == 'Ubuntu':
           os.system("apt-get -y install unzip")
        else:
            print "the system is neither CentOS nor Ubuntu"
            exit(errno.EINVAL)

def check_lsb_release():
    """
    Verify if lsb_release command is available
    """
    args = [ 'which', 'lsb_release', ]
    process = subprocess.Popen(
        args=args,
        stdout=subprocess.PIPE,
        )
    lsb_release_path, _ = process.communicate()
    ret = process.wait()
    if ret != 0:
        raise RuntimeError('The lsb_release command was not found on remote host.  Please install the lsb-release package.')

def lsb_release():
    """
    Get LSB release information from lsb_release.

    Returns truple with distro, release and codename. Otherwise
    the function raises an error (subprocess.CalledProcessError or
    RuntimeError).
    """
    args = [ 'lsb_release', '-s', '-i' ]
    process = subprocess.Popen(
        args=args,
        stdout=subprocess.PIPE,
        )
    distro, _ = process.communicate()
    ret = process.wait()
    if ret != 0:
        raise subprocess.CalledProcessError(ret, args, output=distro)
    if distro == '':
        raise RuntimeError('lsb_release gave invalid output for distro')

    args = [ 'lsb_release', '-s', '-r', ]
    process = subprocess.Popen(
        args=args,
        stdout=subprocess.PIPE,
        )
    release, _ = process.communicate()
    ret = process.wait()
    if ret != 0:
        raise subprocess.CalledProcessError(ret, args, output=release)
    if release == '':
        raise RuntimeError('lsb_release gave invalid output for release')

    args = [ 'lsb_release', '-s', '-c', ]
    process = subprocess.Popen(
        args=args,
        stdout=subprocess.PIPE,
        )
    codename, _ = process.communicate()
    ret = process.wait()
    if ret != 0:
        raise subprocess.CalledProcessError(ret, args, output=codename)
    if codename == '':
        raise RuntimeError('lsb_release gave invalid output for codename')

    return (str(distro).rstrip(), str(release).rstrip(), str(codename).rstrip())


class Setup:
    def __init__(self, v):
        self.verbose = v
        check_lsb_release()
        check_etc_resolv()
	check_unzip()

    def centos_down(self, soft_path, v):
        software = os.listdir(soft_path)
        for soft in software: 
	    file = soft_path + soft
            if soft.endswith(".rpm"):
                cmd = 'rpm -ivh ' + file
                if self.verbose:
                    print cmd
                os.system(cmd)

            if soft == 'disk2lid':
                os.system('cp ' + file + ' /bin/')
                os.system('chmod a+x /bin/ ' + file)
            
            if soft.startswith("lib"):
                cmd = 'cp ' + file + ' /usr/lib/'
                if self.verbose:
                    print cmd
                os.system(cmd)

                cmd = 'cp ' + file + ' /usr/lib64/'
                if self.verbose:
                    print cmd
                os.system(cmd)

                if soft == 'libstorelib.so.4.02-0':
                    print 'libstorelib.so.4.02-0'
                    os.system('ln -s /usr/lib/libstorelib.so.4.02-0 /usr/lib/libstorelib.so')
                    os.system('ln -s /usr/lib/libstorelib.so.4.02-0 /usr/lib/libstorelib.so.4')
                    os.system('ln -s /usr/lib64/libstorelib.so.4.02-0 /usr/lib64/libstorelib.so')
                    os.system('ln -s /usr/lib64/libstorelib.so.4.02-0 /usr/lib64/libstorelib.so.4')

    def ubuntu_down(self, soft_path, v):
        cmd = 'apt-get -y install libaio1 python-paramiko python-ethtool libssl1.0.0  libssl-dev libcrypto++9 libcrypto++-dev libssl0.9.8-dbg ethtool open-iscsi-utils open-iscsi expect  pdsh numactl  libicu48 '
        if self.verbose:
            print cmd
        os.system(cmd)

        software = os.listdir(soft_path)
        print software
        for soft in software:
	    file = soft_path + soft 
            if soft.endswith(".deb"):
                print file
                cmd = 'dpkg -i ' + file
                if self.verbose:
                    print cmd
                os.system(cmd)

    def down(self, v):
        zip = ""
	soft_path = ""

        path = "https://github.com/fusionstack/install/archive/software.zip"
        cmd = "wget " + path
        if self.verbose:
            print cmd

        (status, out) = commands.getstatusoutput(cmd)
        if (out != ''):
            for line in out.splitlines():
                m = re.search('Saving to:\W+(\w+\.?\w+)\W', line)
		if m is not None:
		    zip = m.group(1)
        else:
            print "[status]:",status

        if os.path.isfile(zip):
            cmd = "unzip " + zip
        if self.verbose:
            print cmd
        (status, out) = commands.getstatusoutput(cmd)
	print out
        if (out != ''):
            for line in out.splitlines():
	        m = re.search('\s+creating: (.*)', line)
		if m is not None:
		    soft_path = m.group(1)
        else:
            print "zip was null"
            exit(errno.EINVAL)

        (distro, release, codename) = lsb_release()
        if distro == 'CentOS':
            self.centos_down(soft_path, v)
        elif distro == 'Ubuntu':
            self.ubuntu_down(soft_path, v)
        else:
            print "the system is neither CentOS nor Ubuntu"
            exit(errno.EINVAL)

               
    def install(self, v):
	zip = ""
	tar_path = ""
        path = "https://github.com/fusionstack/install/archive/tar.zip"
        cmd = "wget " + path
        if self.verbose:
            print cmd

	#'''
	(status, out) = commands.getstatusoutput(cmd)
        if (out != ''):
            for line in out.splitlines():
                m = re.search('Saving to:\W+(\w+\.?\w+)\W', line)
		if m is not None:
		    zip = m.group(1)
        else:
            print "[status]:",status
	#'''

	if os.path.isfile(zip):
            cmd = "unzip " + zip
        if self.verbose:
            print cmd
        (status, out) = commands.getstatusoutput(cmd)
	print out
        if (out != ''):
            for line in out.splitlines():
	        m = re.search('\s+creating: (.*)', line)
		if m is not None:
		    tar_path = m.group(1)
		    print "tar_path",tar_path
        else:
            print "zip was null"
            exit(errno.EINVAL)
        
        (distro, release, codename) = lsb_release()
        os.system('mkdir -p  /opt/mds/lich')
        os.system('mkdir -p  /opt/mds/etc')

	print "tar_path",tar_path
        tar = os.listdir(tar_path)
        for soft in tar:
	    file = tar_path + soft 
            if soft.split('.tar.gz')[0].endswith('-U') and distro == 'Ubuntu':
                if soft.startswith('lich-etc'):
                    os.system('tar  xvf ' + file + ' -C  /opt/mds/etc')
                if soft.startswith('lich-testing'):
                    os.system('tar  xvf ' + file + ' -C  /opt/mds/lich')
            if soft.split('.tar.gz')[0].endswith('-C') and distro == 'CentOS':
                if soft.startswith('lich-etc'):
                    os.system('tar  xvf ' + file + ' -C  /opt/mds/etc')
                if soft.startswith('lich-testing'):
                    os.system('tar  xvf ' + file + ' -C  /opt/mds/lich')


def main():
    verbose = 0

    _argv = sys.argv[1:]
    argv = []
    for i in range(len(_argv)):
        if (_argv[i] in ('-v', '--verbose')):
            verbose = 1
        else:
            argv.append(_argv[i])

    try:
        opts, args = getopt.getopt(
                argv,
                'hv', ['help', 'verbose', 'down', 'install']
                )
    except getopt.GetoptError, err:
        print str(err)
        usage()
        exit(errno.EINVAL)

    try:
        setup = Setup(verbose)
    except Exception, e:
        print str(e)
        exit(e)

    for o, a in opts:
        if o in ('-h', '--help'):
            usage()
            exit(0)
        elif o in '--down':
            setup.down(verbose)
        elif o in '--install':
            setup.install(verbose)
        else:
            usage()
            exit(errno.EINVAL)

if __name__ == '__main__':
    if (len(sys.argv) == 1):
        usage()
    else:
        main()
