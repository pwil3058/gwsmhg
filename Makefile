VERSION:=$(subst ',,$(subst VERSION = ',,$(shell grep "VERSION = " setup_generic.py)))
RELEASE=1

RPMREQS:=pygtk2 pygtksourceview pycairo pygobject2 mercurial
RPMBDIR=~/rpmbuild
PREFIX=/usr

SRCS:=$(shell hg status -macdn)
SRCDIST:=gwsmhg-$(VERSION).tar.gz
WINDIST:=gwsmhg-$(VERSION).win32.exe
RPMDIST:=gwsmhg-$(VERSION)-$(RELEASE).noarch.rpm
RPMSRC:=$(RPMBDIR)/SOURCES/$(SRCDIST)
DEBDIR=deb_bld
DEBSPECDIR:=$(DEBDIR)/DEBIAN
DEBSPEC:=$(DEBSPECDIR)/control
DEBREQS:= python python-gtk2 python-gtksourceview2 python-gobject python-cairo mercurial

help:
	@echo "Choices are:"
	@echo "	make source_dist"
	@echo "	make win_dist"
	@echo "	make rpm"
	@echo "	make all_dist"
	@echo "	make install"
	@echo "	make clean"

all_dist: $(SRCDIST)  $(WINDIST) $(RPMDIST)

gwsmhg.spec: setup.py setup_generic.py Makefile
	python setup.py bdist_rpm --build-requires python --spec-only \
		--group "Development/Tools" --release $(RELEASE) \
		--requires "$(RPMREQS)" --dist-dir . \
		--doc-files=COPYING,copyright
	echo "%{_prefix}" >> gwsmhg.spec
	sed -i 's/-f INSTALLED_FILES//' gwsmhg.spec

source_dist: $(SRCDIST)

$(SRCDIST): $(SRCS)
	python setup.py sdist --dist-dir .

win_dist: $(WINDIST)

$(WINDIST):
	python setup.py bdist_wininst --dist-dir .

rpm: $(RPMDIST)

$(RPMSRC): $(SRCDIST)
	cp $(SRCDIST) $(RPMSRC)

$(RPMDIST): $(RPMSRC) gwsmhg.spec
	rpmbuild -bb gwsmhg.spec
	cp $(RPMBDIR)/RPMS/noarch/$(RPMDIST) .

$(DEBSPEC): create_deb_spec setup_generic.py setup.py Makefile
	mkdir -p $(DEBSPECDIR)
	python create_deb_spec $(DEBREQS) > $(DEBSPEC)

deb: $(DEBSPEC) $(SRCS)
	sudo mkdir -p $(DEBDIR)/$(PREFIX)
	sudo python setup_deb.py install --prefix $(DEBDIR)/$(PREFIX)
	dpkg-deb --build $(DEBDIR) .

install:
	python setup.py install --prefix=$(PREFIX)

clean:
	-rm *.rpm *.spec *.exe *.tar.gz MANIFEST
	-rm -r build
