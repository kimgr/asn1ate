# This is asn2quickder, an ASN.1 compiler with Quick DER backend
#
# Quick DER is a small and efficient library for DER parsing, possible
# entirely without memory allocation in the routines.  This makes it
# perfect for many embedded uses, and the occasional quick actions on ASN.1
# encoded in DER, such as plucking fields out of a certificate or ticket.
#
# This basically is a Python script that invokes a few library routines.
# These install into $(DESTDIR)$(PREFIX)/lib/asn2quickder/asn1ate
# where the reason for the asn2quickder prefix is to avoid naming conflicts
# with any "real" asn1ate intallation; asn2quickder is a branch off asn1ate.
#
# References:
# https://github.com/vanrein/asn2quickder
# https://github.com/kimgr/asn1ate
# https://github.com/vanrein/quick-der
#
# From: Rick van Rein <rick@openfortress.nl>


DESTDIR ?=
PREFIX ?= /usr/local

SUBDIR=asn1ate

BINS=asn2quickder
LIBS=__init__ parser sema support/pygen

all: $(foreach lib,$(LIBS),$(SUBDIR)/$(lib).pyc)

%.pyc: %.py
	PYTHONPATH=$(SUBDIR)/..:$(PYTHONPATH) python -c 'import asn1ate.$(basename $(subst /,.,$(subst $(SUBDIR)/,,$<)))'

%.pyo: %.pyc
	PYTHONPATH=$(SUBDIR)/..:$(PYTHONPATH) python -O $<

clean:
	rm -f $(foreach lib,$(LIBS),$(SUBDIR)/$(lib).pyc)
	rm -f $(foreach lib,$(LIBS),$(SUBDIR)/$(lib).pyo)

install: all
	mkdir -p '$(DESTDIR)/$(PREFIX)/lib/asn2quickder/asn1ate/support'
	$(foreach file,$(LIBS),install $(SUBDIR)/$(file).py  '$(DESTDIR)$(PREFIX)/lib/asn2quickder/asn1ate/$(file).py'  &&) echo 'Python library files installed'
	$(foreach file,$(LIBS),install $(SUBDIR)/$(file).pyc '$(DESTDIR)$(PREFIX)/lib/asn2quickder/asn1ate/$(file).pyc' &&) echo 'Python optimised library files installed'
	$(foreach file,$(BINS),install $(SUBDIR)/$(file).py  '$(DESTDIR)$(PREFIX)/lib/asn2quickder/asn1ate/$(file).py'  &&) echo 'Python binary files installed'
	( echo '#!/bin/sh' ; echo 'PYTHONPATH='"'"'$(DESTDIR)/$(PREFIX)/lib/asn2quickder:$(PYTHONPATH)'"'"' python '"'"'$(DESTDIR)/$(PREFIX)/lib/asn2quickder/asn1ate/asn2quickder.py'"'"' "$$@"' ) > '$(DESTDIR)$(PREFIX)/bin/asn2quickder'
	chmod ugo+x '$(DESTDIR)$(PREFIX)/bin/asn2quickder'

uninstall:
	rm -f '$(DESTDIR)$(PREFIX)/bin/asn2quickder'
	rm -rf '$(DESTDIR)$(PREFIX)/lib/asn2quickder'


