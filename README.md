# 说明
代码及具体的安装步骤见CGRAN的[Two-Way Relaying with Network Coding](https://www.cgran.org/wiki/RelayingSchemesImplementation)项目。CGRAN上面是基于svn，通过git svn转换为git。此外修正了一点安装上的Errors。


# 关键参数

*  [GNURadio v3.2.2](http://gnuradio.org/redmine/attachments/download/364/gnuradio-3.2.2.tar.gz)
* [Reed-Solomon Python Extension Module](http://hathawaymix.org/Software/ReedSolomon/)


# FAQs

## Installation Errors

>  spectrumdisplayform_moc.cc:14:2: error: #error "This file was generated using the moc from 4.5.0. It"
spectrumdisplayform_moc.cc:15:2: error: #error "cannot be used with
the include files from this version of Qt."
spectrumdisplayform_moc.cc:16:2: error: #error "(The moc has changed too 
much.)"

Solution: reconfiguration like [this](http://www.ruby-forum.com/topic/206439) 

$ `make clean`

$ `./bootstrap`


### Running Errors

> ImportError: No module named _tkinter

Solution: Install the python-tk package (for Ubuntu)

$ `sudo apt-get install python-tk`

> Error: Directory including modulation schemes not found! Check the absolute path in my_gnuradio/blks2/__init__.py! /home/iot/git/relaying_schemes_implementation/trunk/my_gnuradio/blk2

Solution: Change absolute path in variable p in ../my_gnuradio/blks2/__init__.py in order to make it point to the location where this file is located.

> ImportError: No module named blks2impl.logpwrfft

Solution: 

$ `exec "from blks2impl.%s import *" % (f,)`
=> 

$ `exec "from my_gnuradio.blks2impl.%s import *" % (f,)`

> ImportError: No module named usrp_options

> ImportError: No module named generic_usrp

> ImportError: No module named pick_bitrate

Solution: copy usrp_options.py, generic_usrp.py, pick_bitrate.py from gnuradio-examples/digital/
