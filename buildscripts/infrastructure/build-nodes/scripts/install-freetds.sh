#!/bin/bash
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

set -e -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
# shellcheck source=buildscripts/infrastructure/build-nodes/scripts/build_lib.sh
. "${SCRIPT_DIR}/build_lib.sh"

FREETDS_VERSION=1.4.22
DIR_NAME=freetds-${FREETDS_VERSION}
ARCHIVE_NAME=${DIR_NAME}.tgz
TARGET_DIR="${TARGET_DIR:-/opt}"

# Increase this to enforce a recreation of the build cache
BUILD_ID=1

build_package() {
    mkdir -p "$TARGET_DIR/src"
    cd "$TARGET_DIR/src"

    # Get the sources from nexus or upstream
    mirrored_download "${ARCHIVE_NAME}" "https://www.freetds.org/files/stable/freetds-${FREETDS_VERSION}.tar.gz"

    # Now build the package
    tar xf "${ARCHIVE_NAME}"
    cd "${DIR_NAME}"
    ./configure \
        --enable-msdblib \
        --prefix="${TARGET_DIR}/${DIR_NAME}" \
        --sysconfdir=/etc/freetds \
        --with-tdsver=7.1 \
        --disable-apps \
        --disable-server \
        --disable-pool \
        --disable-odbc
    make -j4
    make install

    cd "$TARGET_DIR"
    rm -rf "$TARGET_DIR/src"
}

register_library() {
    log "Register library"
    echo "${TARGET_DIR}/${DIR_NAME}/lib" >/etc/ld.so.conf.d/freetds.conf
    ldconfig
    cp -pr --no-dereference "${TARGET_DIR}/${DIR_NAME}/lib/"* /usr/lib
    cp -pr "${TARGET_DIR}/${DIR_NAME}/include/"* /usr/include
}

if [ "$1" != "link-only" ]; then
    cached_build "${TARGET_DIR}" "${DIR_NAME}" "${BUILD_ID}" "${DISTRO}" "${BRANCH_VERSION}"
fi
register_library
