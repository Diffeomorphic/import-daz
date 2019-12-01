# Copyright (c) 2016-2019, Thomas Larsson
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer
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
import importlib
import sys
import bpy
if bpy.app.version < (2,80,0):
    from .buttons27 import NameString
else:
    from .buttons28 import NameString

#----------------------------------------------------------
#   Load addons
#----------------------------------------------------------

theAddons = {}

def loadEnabledAddons():
    import json
    from .fileutils import safeOpen
    filepath = getAddonsList()
    try:
        with open(filepath, "r") as fp:
            struct = json.load(fp)
    except:
        return
    if "daz-addons" in struct.keys():
        loadAddons(struct["daz-addons"], {}, True)


def getAddonsList():
    from .fileutils import getHomeDir
    if bpy.app.version < (2,80,0):
        return getHomeDir() + "/import-daz-addons-27x.json"
    else:
        return getHomeDir() + "/import-daz-addons-28x.json"


def loadAllAddons():
    mnames = []
    folder = os.path.join(os.path.dirname(__file__), "addons")
    for file in os.listdir(folder):
        path = os.path.join(folder, file)
        if os.path.isdir(path):
            if "__init__.py" in os.listdir(path):
                mnames.append([file,False])
        else:
            pair = os.path.splitext(file)
            if len(pair) == 2:
                mname,ext = pair
            else:
                continue
            if (ext == ".py" and
                file != "__init__.py"):
                mnames.append([mname,False])
    loadAddons(mnames, theAddons, False)


def loadAddons(mnames, oldAddons, default):
    global theAddons
    theAddons = {}
    anchor = os.path.basename(__file__[0:-9]) + ".addons"
    for mname,show in mnames:
        print("Loading addon %s ... " % mname, end="", flush=True)
        fullname = anchor + "." + mname
        old = (fullname in sys.modules.keys())
        try:
            module = importlib.import_module("." + mname, anchor)
            print("OK")
        except:
            type,value,tb = sys.exc_info()
            print("Failed\n  because %s" % value)
            continue
        if old:
            print("Reload %s ..." % module.__name__, end="", flush=True)
            try:
                importlib.reload(module)
                print("OK")
            except:
                type,value,tb = sys.exc_info()
                print("Failed\n  because %s" % value)
                continue
        if hasattr(module, "bl_info"):
            bl_info = getattr(module, "bl_info")
            bl_info["file"] = module.__file__
            if "name" not in bl_info.keys():
                bl_info["name"] = mname
            enable = default
            if mname in oldAddons.keys():
                _,enable,show,_ = oldAddons[mname]
            theAddons[mname] = (module,enable,show,bl_info)
        else:
            print("Module %s has no bl_info." % mname)


def registerAddon(module):
    try:
        module.register()
    except:
        type,value,tb = sys.exc_info()
        print("Could not register addon %s because %s" % (module.__name__, value))


def unregisterAddon(module):
    try:
        module.unregister()
    except:
        type,value,tb = sys.exc_info()
        print("Could not unregister addon %s because %s" % (module.__name__, value))


class DAZ_OT_EnableAddon(bpy.types.Operator, NameString):
    bl_idname = "daz.enable_addon"
    bl_label = ""
    bl_description = "Enable/Disable add-on"

    def execute(self, context):
        global theAddons
        module,enabled,show,bl_info = theAddons[self.name]
        if enabled:
            theAddons[self.name] = module,False,show,bl_info
            unregisterAddon(module)
            print("Add-on %s disabled" % self.name)
        else:
            theAddons[self.name] = module,True,show,bl_info
            registerAddon(module)
            print("Add-on %s enabled" % self.name)
        return{'FINISHED'}


class DAZ_OT_ShowAddon(bpy.types.Operator, NameString):
    bl_idname = "daz.show_addon"
    bl_label = ""
    bl_description = "Show/Hide add-on"

    def execute(self, context):
        global theAddons
        module,enabled,show,bl_info = theAddons[self.name]
        if show:
            theAddons[self.name] = module,enabled,False,bl_info
        else:
            theAddons[self.name] = module,enabled,True,bl_info
        return{'FINISHED'}


class DAZ_OT_SaveAddons(bpy.types.Operator, NameString):
    bl_idname = "daz.save_addons"
    bl_label = "Save Settings"
    bl_description = "Save add-ons settings"

    def execute(self, context):
        import json
        from .fileutils import getHomeDir, safeOpen
        addons = []
        for key in theAddons.keys():
            _,enabled,show,_ = theAddons[key]
            if enabled:
                addons.append([key, show])
        struct = {"daz-addons" : addons}
        string = json.dumps(struct, sort_keys=True, indent=2, ensure_ascii=False)
        filepath = getAddonsList()
        with safeOpen(filepath, "w", dirMustExist=True, mustOpen=True) as fp:
            fp.write(string)
        print("Settings file %s saved" % filepath)
        return{'FINISHED'}


class DAZ_OT_RefreshAddons(bpy.types.Operator, NameString):
    bl_idname = "daz.refresh_addons"
    bl_label = "Refresh"
    bl_description = "Reload add-ons"

    def execute(self, context):
        loadAllAddons()
        return{'FINISHED'}

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_EnableAddon,
    DAZ_OT_ShowAddon,
    DAZ_OT_SaveAddons,
    DAZ_OT_RefreshAddons,
]

def initialize():
    global theAddons
    for cls in classes:
        bpy.utils.register_class(cls)
    for module,enabled,show,bl_info in theAddons.values():
        if enabled:
            registerAddon(module)


def uninitialize():
    global theAddons
    for cls in classes:
        bpy.utils.unregister_class(cls)
    for module,enabled,show,bl_info in theAddons.values():
        if enabled:
            unregisterAddon(module)
