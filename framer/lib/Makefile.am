#
# Copyright 2004,2005,2006,2008,2009,2010 Free Software Foundation, Inc.
# 
# This file is part of GNU Radio
# 
# GNU Radio is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
# 
# GNU Radio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with GNU Radio; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
# 

include $(top_srcdir)/Makefile.common

# list of programs run by "make check" and "make distcheck"
TESTS = test_all

# ----------------------------------------------------------------
# framer C++ library: libgnuradio-framer.so
# ----------------------------------------------------------------

# C/C++ headers get installed in ${prefix}/include/$(modname)
modinclude_HEADERS = \
	framer_sink_rs.h

lib_LTLIBRARIES = libgnuradio-framer.la

libgnuradio_framer_la_SOURCES = \
	framer_sink_rs.cc

libgnuradio_framer_la_LIBADD = \
	$(GNURADIO_CORE_LA)

libgnuradio_framer_la_LDFLAGS = \
	$(NO_UNDEFINED)

# ----------------------------------------------------------------
# framer C++ QA library: libgnuradio-framer-qa.so (not installed)
# ----------------------------------------------------------------

noinst_LTLIBRARIES = libgnuradio-framer-qa.la

libgnuradio_framer_qa_la_SOURCES = \
	qa_framer.cc \
	qa_framer_square_ff.cc

libgnuradio_framer_qa_la_LDFLAGS = $(NO_UNDEFINED) -version-info 0:0:0

libgnuradio_framer_qa_la_LIBADD = \
	libgnuradio-framer.la \
	$(CPPUNIT_LIBS)

# ----------------------------------------------------------------
# headers that don't get installed
# ----------------------------------------------------------------
noinst_HEADERS = \
	qa_framer.h \
	qa_framer_square_ff.h 

# ----------------------------------------------------------------
# test program
# ----------------------------------------------------------------
noinst_PROGRAMS = \
	test_all

test_all_SOURCES = test_all.cc
test_all_LDADD   = libgnuradio-framer-qa.la
