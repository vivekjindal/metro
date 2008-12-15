[section steps]

chroot/prerun: [
#!/bin/bash
rm -f /etc/make.profile
ln -sf ../usr/portage/profiles/$[portage/profile] /etc/make.profile || exit 1
echo "Set Portage profile to $[portage/profile]."
]

#[option parse/lax]

setup: [
/usr/sbin/env-update
gcc-config 1
source /etc/profile
export MAKEOPTS="$[portage/MAKEOPTS]"
export EMERGE_WARNING_DELAY=0
export CLEAN_DELAY=0
export EBEEP_IGNORE=0
export EPAUSE_IGNORE=0
export CONFIG_PROTECT="-* /etc/locale.gen"
if [ -d /var/tmp/ccache ] 
then
	! [ -e /usr/bin/ccache ] && emerge --oneshot --nodeps ccache
	export CCACHE_DIR=/var/tmp/ccache
	export FEATURES="ccache"

	# The ccache ebuild has a bug where it will install links in /usr/lib/ccache/bin to reflect the current setting of CHOST.
	# But the current setting of CHOST may not reflect the current compiler available (remember, CHOST can be overridden in /etc/make.conf)
	
	# This causes problems with ebuilds (such as ncurses) who may find an "i686-pc-linux-gnu-gcc" symlink in /usr/lib/ccache/bin and 
	# assume that an "i686-pc-linux-gnu-gcc" compiler is actually installed, when we really have an i486-pc-linux-gnu-gcc compiler 
	# installed. For some reason, ncurses ends up looking for the compiler in /usr/bin and it fails - no compiler found.

	# It's a weird problem but the next few ccache-config lines takes care of it by removing bogus ccache symlinks and installing
	# valid ones that reflect the compiler that is actually installed on the system - so if ncurses sees an "i686-pc-linux-gnu-gcc"
	# in /usr/lib/ccache/bin, it looks for (and finds)  a real i686-pc-linux-gnu-gcc installed in /usr/bin.

	# I am including these detailed notes so that people are aware of the issue and so we can look for a more elegant solution to
	# this problem in the future. This problem crops up when you are using an i486-pc-linux-gnu CHOST stage3 to create an 
	# i686-pc-linux-gnu CHOST stage1. It will probably crop up whenever the CHOST gets changed. For now, it's fixed :)

	for x in i386 i486 i586 i686 x86_64
	do
		ccache-config --remove-links $x-pc-linux-gnu
	done
	gccprofile="`gcc-config -c`"
	gccchost=`gcc-config -S $gccprofile | cut -f1 -d" "`
	echo "Setting ccache links to: $gccchost"
	ccache-config --install-links $gccchost
fi
# the quotes below prevent variable expansion of anything inside make.conf
cat > /etc/make.conf << "EOF"
$[[files/make.conf]]
EOF
if [ "$[portage/files/package.use?]" = "yes" ]
then
cat > /etc/portage/package.use << "EOF"
$[[portage/files/package.use:lax]]
EOF
fi
if [ "$[portage/files/package.keywords?]" = "yes" ]
then
cat > /etc/portage/package.keywords << "EOF"
$[[portage/files/package.keywords:lax]]
EOF
fi
if [ "$[probe/setup?]" = "yes" ]
then
$[[probe/setup:lax]]
fi
]

#[option parse/strict]

chroot/clean: [
#!/bin/bash
# We only do this cleanup if ROOT = / - in other words, if we are going to be packing up /,
# then we need to remove the custom configuration we've done to /. If we are building a 
# stage1, then everything is in /tmp/stage1root so we don't need to do this.
export ROOT=$[portage/ROOT]
if [ "${ROOT}" = "/" ]
then
	# remove our tweaked configuration files, restore originals.
	for f in /etc/profile.env /etc/csh.env /etc/env.d/99zzmetro
	do
		echo "Cleaning chroot: $f..."
		rm -f $f || exit 1
	done
	for f in /etc/resolv.conf /etc/hosts
	do
		[ -e $f ] && rm -f $f
		if [ -e $f.orig ] 
		then
			mv -f $f.orig $f || exit 2
		fi
	done
else
	# stage1 - make sure we include our make.conf and profile link...
	rm -f $ROOT/etc/make.conf $ROOT/etc/make.profile || exit 3
	cp -a /etc/make.conf /etc/make.profile $ROOT/etc || exit 4
fi
# clean up temporary locations. Note that this also ends up removing our scripts, which
# exist in /tmp inside the chroot. So after this cleanup, any execution inside the chroot
# won't work. This is normally okay.

rm -rf $ROOT/var/tmp/* $ROOT/tmp/* $ROOT/root/* $ROOT/usr/portage $ROOT/var/log/* || exit 5
install -d $ROOT/etc/portage

# ensure that make.conf.example is set up OK...
if [ ! -e $ROOT/etc/make.conf.example ]
then
	if [ -e $ROOT/usr/share/portage/config/make.conf.example ]
	then
		ln -s ../usr/share/portage/config/make.conf.example $ROOT/etc/make.conf.example || exit 6
	fi
fi
]

# do any cleanup that you need with things bind mounted here:

chroot/postrun: [
#!/bin/bash
$[[steps/setup]]
if [ "$[target]" != "stage1" ] && [ -e /usr/bin/ccache ] 
then
	emerge -C dev-util/ccache 
fi
]

unpack: [
#!/bin/bash
[ ! -d $[path/chroot] ] && install -d $[path/chroot] 
[ ! -d $[path/chroot]/tmp ] && install -d $[path/chroot]/tmp --mode=1777 || exit 2
echo -n "Extracting source stage $[path/mirror/source]"
if [ -e /usr/bin/pbzip2 ]
then
	echo " using pbzip2..."
	# Use pbzip2 for multi-core acceleration
	pbzip2 -dc $[path/mirror/source] | tar xpf - -C $[path/chroot] || exit 3
	[ ! -d $[path/chroot]/usr/portage ] && install -d $[path/chroot]/usr/portage --mode=0755
	echo "Extracting portage snapshot $[path/mirror/snapshot] using pbzip2..."
	pbzip2 -dc $[path/mirror/snapshot] | tar xpf - -C $[path/chroot]/usr || exit 4	
else
	echo "..."
	tar xjpf $[path/mirror/source] -C $[path/chroot] || exit 3
	[ ! -d $[path/chroot]/usr/portage ] && install -d $[path/chroot]/usr/portage --mode=0755
	echo "Extracting portage snapshot $[path/mirror/snapshot]..."
	tar xjpf $[path/mirror/snapshot] -C $[path/chroot]/usr || exit 4
fi
# support for "live" git snapshot tarballs:
if [ -e $[path/chroot]/usr/portage/.git ]
then
	( cd $[path/chroot]/usr/portage; git checkout $[git/branch] || exit 50 )
fi
cat << "EOF" > $[path/chroot]/etc/make.conf || exit 5
$[[files/make.conf]]
EOF
cat << "EOF" > $[path/chroot]/etc/env.d/99zzmetro || exit 6
$[[files/proxyenv]]
EOF
cat << "EOF" > $[path/chroot]/etc/locale.gen || exit 7
$[[files/locale.gen]]
EOF
for f in /etc/resolv.conf /etc/hosts
do
	if [ -e $f ] 
	then
		respath=$[path/chroot]$f
		if [ -e $respath ]
		then
			echo "Backing up $respath..."
			cp $respath ${respath}.orig 
			if [ $? -ne 0 ]
			then
				 echo "couldn't back up $respath" && exit 8
			fi
		fi
		echo "Copying $f to $respath..."
		cp $f $respath 
		if [ $? -ne 0 ]
		then
			echo "couldn't copy $f into place"
			exit 9
		fi
	fi
done
]

capture: [
#!/bin/bash
outdir=`dirname $[path/mirror/target]`
if [ ! -d $outdir ]
then
	install -d $outdir || exit 1
fi
if [ -e /usr/bin/pbzip2 ]
then
	# multi-core friendly pbzip2 option...
	echo "Creating $[path/mirror/target] using pbzip2..."
	tarout="$[path/mirror/target]"
	tarout="${tarout%.*}"
	tar cpf $tarout -C $[path/chroot/stage] . 
	if [ $? -ge 2 ]
	then
		rm -f "$tarout" "$[path/mirror/target]"
		exit 1
	else
		pbzip2 -p4 $tarout || exit 2
	fi
else
	echo "Creating $[path/mirror/target]..."
	tar cjpf $[path/mirror/target] -C $[path/chroot/stage] .
	if [ $? -ge 2 ]
	then
		rm -f $[path/mirror/target]
		exit 1
	fi
fi
]