#!/bin/bash

TEMP="$(create_directory -t)"

if [ "$1" = "" -o "${1//[0-9]/}" = "${1}" ]; then
	echo "Usage: $0 <minor>"
	exit 1
fi

FIRST_SECT="$(echo "$TEMP" | sed -n "s#^partition[ \t]\{1,\}$1:[ \t]\{1,\}\([0-9]\{1,\}\)-[0-9]\{1,\}.*#\1# p" | sort -u)"

if [ "${FIRST_SECT}" = "" ]; then
	echo "No partition $1 found"
	exit 1
elif [ "${FIRST_SECT//[0-9]/}" != "" ]; then
	echo "Could not determine first section of partition $1 found"
	exit 1
fi

echo "Make partition $1 unusable with destroying section $FIRST_SECT"
dd if=/dev/zero of=/dev/igfdisk seek=$((256*1024*FIRST_SECT)) oflag=seek_bytes,sync bs=156 count=1
