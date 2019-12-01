# Copyright (c) 2016-2019, Thomas Larsson
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.

import os
import json
import gzip
from .settings import theSettings
from .error import DazError


def readAssetFile(filepath):
    ext = os.path.splitext(filepath)[1]
    if ext in [".duf", ".dsf"]:
        return readDufFile(filepath, False)
    elif ext == ".pz2":
        return readPz2File(filepath, False)

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def readDufFile(filepath, haltOnFail=True):
    from .fileutils import safeOpen
    try:
        with gzip.open(filepath, 'rb') as fp:
            bytes = fp.read()
    except IOError:
        bytes = None

    if bytes:
        string = bytes.decode("utf-8")
        struct = json.loads(string)
    else:
        fp = safeOpen(filepath, "rU")
        if fp is None:
            if theSettings.verbosity < 2:
                return {}
            paths = filepath.split("/")
            for n in range(2, len(paths)):
                path = "/".join(paths[0:n])
                print(path, os.path.isdir(path))
            msg = ("File not found:\n%s      " % filepath)
            if theSettings.verbosity > 2:
                raise DazError(msg)
            return {}

        try:
            string = "".join(list(fp))
            fp.close()
            cannotDecode = False
        except UnicodeDecodeError:
            cannotDecode = True

        if cannotDecode:
            msg = ("This file is corrupt:\n  '%s'" % filepath)
            if theSettings.verbosity > 1:
                print(msg)
            elif theSettings.verbosity > 2:
                raise DazError(msg)
            return {}

        try:
            struct = json.loads(string)
        except json.JSONDecodeError:
            struct = {}

    # Try removing stray characters in beginning and end of file
    if not struct:
        while len(string) > 0 and string[0] != '{':
            string = string[1:]
        while len(string) > 0 and string[-1] != '}':
            string = string[:-1]
        try:
            struct = json.loads(string)
        except json.JSONDecodeError:
            struct = {}

    if not struct and haltOnFail:
        print(string[0:100])
        raise DazError("Could not load duf %s" % filepath)

    return struct

