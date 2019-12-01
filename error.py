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


import bpy

theMessage = "No message"
theErrorLines = []

class ErrorOperator(bpy.types.Operator):
    bl_idname = "daz.error"
    bl_label = "Daz Importer"

    def execute(self, context):
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        global theMessage, theErrorLines
        theErrorLines = theMessage.split('\n')
        maxlen = len(self.bl_label)
        for line in theErrorLines:
            if len(line) > maxlen:
                maxlen = len(line)
        width = 20+5*maxlen
        height = 20+5*len(theErrorLines)
        #self.report({'INFO'}, theMessage)
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=width, height=height)

    def draw(self, context):
        global theErrorLines
        for line in theErrorLines:
            self.layout.label(text=line)


class DazError(Exception):

    def __init__(self, value, warning=False):
        global theMessage
        if warning:
            theMessage = "WARNING:\n" + value
        else:
            theMessage = "ERROR:\n" + value
        bpy.ops.daz.error('INVOKE_DEFAULT')

    def __str__(self):
        global theMessage
        return repr(theMessage)


def reportError(msg, instances={}, warnPaths=False):
    global theUseDumpErrors, theInstances
    from .settings import theSettings
    if theSettings.verbosity > 2:
        theUseDumpErrors = True
        theInstances = instances
        if warnPaths:
            msg += ("\nHave all DAZ library paths been set up correctly?\n" +
                    "See https://diffeomorphic.blogspot.se/p/setting-up-daz-library-paths.html         ")
        msg += ("\nFor details see\n'%s'" % getErrorPath())
        raise DazError(msg)
    elif theSettings.verbosity > 1:
        print(msg)
    return None


def raiseOrReportError(msg, vraise, vrep, error=True):
    from .settings import theSettings
    if theSettings.verbosity > vrep:
        reportError(msg)
    elif theSettings.verbosity > vraise:
        if error:
            raise DazError(msg)
        else:
            print(msg)


def getErrorPath():
    import os
    from .settings import theSettings
    return os.path.realpath(os.path.expanduser(theSettings.errorPath))


def handleDazError(context):
    global theMessage, theUseDumpErrors, theInstances
    import sys, traceback

    if not theUseDumpErrors:
        return
    theUseDumpErrors = False

    type,value,tb = sys.exc_info()
    filepath = getErrorPath()
    try:
        fp = open(filepath, "w", encoding="utf-8")
    except:
        print("Could not write to %s" % filepath)
        return
    fp.write(theMessage)

    fp.write("\n\nTRACEBACK:\n")
    traceback.print_tb(tb, 30, fp)

    try:
        from .settings import theTrace
        from .asset import theAssets, theDazPaths

        fp.write("\n\nFILES VISITED:\n")
        for string in theTrace:
            fp.write("  %s\n" % string)

        fp.write("\nINSTANCES:\n")
        refs = list(theInstances.keys())
        refs.sort()
        for ref in refs:
            fp.write('"%s":    %s\n' % (ref, theInstances[ref]))

        fp.write("\nASSETS:\n")
        refs = list(theAssets.keys())
        refs.sort()
        for ref in refs:
            fp.write('"%s"\n    %s\n\n' % (ref, theAssets[ref]))

        fp.write("\nDAZ ROOT PATHS:\n")
        for n, path in enumerate(theDazPaths):
            fp.write('%d:   "%s"\n' % (n, path))

        fp.write("\nSETTINGS:\n")
        settings = []
        scn = bpy.context.scene
        for attr in dir(scn):
            if attr[0:3] == "Daz":
                value = getattr(scn, attr)
                if (isinstance(value, int) or
                    isinstance(value, float) or
                    isinstance(value, str) or
                    isinstance(value, bool)):
                    settings.append((attr, value))
        settings.sort()
        for attr,value in settings:
            if isinstance(value, str):
                value = ('"%s"' % value)
            fp.write('%25s:    %s\n' % (attr, value))

    except:
        pass

    finally:
        fp.write("\n")
        fp.close()
        print(theMessage)


theUseDumpErrors = False

#-------------------------------------------------------------
#   Debug logging
#-------------------------------------------------------------

theLogFp = None

def logOpen(scn):
    global theLogFp
    if scn.DazLogging:
        theLogFp = safeOpen("/home/dazlog.txt", "w")
    else:
        theLogFp = None

def logClose():
    global theLogFp
    if theLogFp:
        theLogFp.close()
        theLogFp = None

def logLine(line):
    global theLogFp
    if theLogFp:
        theLogFp.write(line)

