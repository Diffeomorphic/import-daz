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
import os
from bpy.props import *
from .settings import theSettings
from .error import *
if bpy.app.version < (2,80,0):
    from .buttons27 import SingleFile, JsonFile, JsonExportFile
else:
    from .buttons28 import SingleFile, JsonFile, JsonExportFile

#-------------------------------------------------------------
#   Open and check for case change
#-------------------------------------------------------------

def safeOpen(filepath, rw, dirMustExist=False, fileMustExist=False, mustOpen=False):
    if dirMustExist:
        folder = os.path.dirname(filepath)
        if not os.path.exists(folder):
            msg = ("Directory does not exist:      \n" +
                   "%s          " % folder)
            raise DazError(msg)

    if fileMustExist:
        if not os.path.exists(filepath):
            msg = ("File does not exist:      \n" +
                   "%s          " % filepath)
            raise DazError(msg)

    try:
        fp = open(filepath, rw, encoding="utf-8")
    except FileNotFoundError:
        fp = None

    if fp is None:
        if rw[0] == "r":
            mode = "reading"
        else:
            mode = "writing"
        msg = ("Could not open file for %s:   \n" % mode +
               "%s          " % filepath)
        if mustOpen:
            raise DazError(msg)
        elif theSettings.verbosity > 4:
            return reportError(msg, warnPaths=True)
        elif theSettings.verbosity > 2:
            print(msg)
    return fp

#-------------------------------------------------------------
#   Open and check for case change
#-------------------------------------------------------------

def getFolder(ob, scn, subdirs):
    from .asset import getDazPath, setDazPaths
    setDazPaths(scn)
    if ob is None:
        return None
    fileref = ob.DazUrl.split("#")[0]
    if len(fileref) < 2:
        return None
    folder = os.path.dirname(fileref)
    basedir = getDazPath(folder)
    if basedir is None:
        return None
    for subdir in subdirs:
        folder = os.path.join(basedir, subdir)
        if os.path.exists(folder):
            return folder
    return None

#-------------------------------------------------------------
#   Path to Documents folder on various Windows systems
#-------------------------------------------------------------

def getMyDocuments():
    import sys
    if sys.platform == 'win32':
        import winreg
        try:
            k = winreg.HKEY_CURRENT_USER
            for x in ['Software', 'Microsoft', 'Windows', 'CurrentVersion', 'Explorer', 'Shell Folders']:
                k = winreg.OpenKey(k, x)

            name, type = winreg.QueryValueEx(k, 'Personal')

            if type == 1:
                #print("Found My Documents folder: %s" % name)
                return name
        except Exception as e:
            print("Did not find path to My Documents folder")

    return os.path.expanduser("~")

"""
import winreg

def subkeys(key):
    i = 0
    while True:
        try:
            subkey = winreg.EnumKey(key, i)
            yield subkey
            i+=1
        except WindowsError as e:
            break

def traverse_registry_tree(fp, hkey, keypath, tabs=0):
    try:
        key = winreg.OpenKey(hkey, keypath, 0, winreg.KEY_READ)
    except PermissionError:
        return
    for subkeyname in subkeys(key):
        fp.write("  "*tabs + subkeyname + "\n")
        subkeypath = "%s\\%s" % (keypath, subkeyname)
        traverse_registry_tree(fp, hkey, subkeypath, tabs+1)

keypath = r"SOFTWARE\\Microsoft\\Windows"

with safeOpen("/home/hkeys.txt", "w") as fp:
    traverse_registry_tree(fp, winreg.HKEY_LOCAL_MACHINE, keypath)
"""

#-------------------------------------------------------------
#   Multifiles
#-------------------------------------------------------------

def getMultiFiles(self, extensions):
    paths = []
    for file_elem in self.files:
        filepath = os.path.join(self.directory, file_elem.name)
        if os.path.isfile(filepath):
            path = getFilePath(filepath, extensions)
            if path:
                paths.append(path)
    return paths


def getFilePath(filepath, exts):
    words = os.path.splitext(filepath)
    if len(words) == 2:
        fname,ext = words
    else:
        return None
    if ext in [".png", ".jpeg", ".jpg", ".bmp"]:
        if os.path.exists(fname):
            words = os.path.splitext(fname)
            if (len(words) == 2 and
                words[1][1:] in exts):
                return fname
        for ext1 in exts:
            path = fname+"."+ext1
            if os.path.exists(path):
                return path
        return None
    elif ext[1:].lower() in exts:
        return filepath
    else:
        return None

#-------------------------------------------------------------
#   Save settings
#-------------------------------------------------------------

def getHomeDir():
    home = os.path.realpath(os.path.expanduser("~"))
    if not os.path.exists(home):
        home = os.path.realpath(os.path.dirname(__file__)) + "/data"
    return home


def getSettingsFile():
    if bpy.app.version < (2,80,0):
        path = getHomeDir() + "/import-daz-settings-27x.json"
    else:
        path = getHomeDir() + "/import-daz-settings-28x.json"
    return path


def saveSettings(filepath, scn):
    import json

    filepath = os.path.splitext(filepath)[0] + ".json"
    settings = {}
    for attr in dir(scn):
        if attr[0:3] == "Daz":
            value = getattr(scn, attr)
            if (isinstance(value, int) or
                isinstance(value, float) or
                isinstance(value, str) or
                isinstance(value, bool)):
                settings[attr] = value
    struct = {"daz-settings" : settings}
    string = json.dumps(struct, sort_keys=True, indent=2, ensure_ascii=False)
    string = string.replace("\\\\", "/")
    string = string.replace("\\", "/")
    with safeOpen(filepath, "w", dirMustExist=True, mustOpen=True) as fp:
        fp.write(string)
    print("Settings file %s saved" % filepath)


class DAZ_OT_SaveDefaultSettings(bpy.types.Operator):
    bl_idname = "daz.save_default_settings"
    bl_label = "Save Default Settings"
    bl_description = "Save current settings as default"
    bl_options = {'UNDO'}

    def execute(self, context):
        try:
            filepath = getSettingsFile()
            saveSettings(filepath, context.scene)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}


class DAZ_OT_SaveSettingsFile(bpy.types.Operator, SingleFile, JsonExportFile):
    bl_idname = "daz.save_settings_file"
    bl_label = "Save Settings File"
    bl_description = "Save current settings to file"
    bl_options = {'UNDO'}

    def execute(self, context):
        try:
            saveSettings(self.filepath, context.scene)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}


    def invoke(self, context, event):
        self.properties.filepath = os.path.dirname(getSettingsFile()) + "/"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

#-------------------------------------------------------------
#   Load settings
#   Called on boot with scn = None
#   Called by button with scn
#-------------------------------------------------------------

def loadLines(settings, scn):
    for key,value in settings.items():
        try:
            _,struct = getattr(bpy.types.Scene, key)
        except AttributeError:
            #print("Missing scene prop: %s" % key)
            continue
        proptype = getPropType(struct, value)
        if not proptype:
            print("Cannot set %s to %s" % (key, value))
            continue
        if scn is not None:
            setattr(scn, key, value)
        else:
            struct["default"] = value
            string = "bpy.types.Scene.%s = %s(" % (key, proptype)
            for key,value in struct.items():
                if key == "attr":
                    pass
                elif isinstance(value, str):
                    string += ' %s="%s",' % (key, value)
                else:
                    string += ' %s=%s,' % (key, value)
            string = string[:-1] + ")"
            string = string.replace("\n", "\\n")
            exec(string)


def loadSettings(filepath, scn):
    fp = safeOpen(filepath, "r", True, True, True)
    if fp:
        loadSettingsFile(fp, filepath, scn)
        fp.close()


def loadSettingsDefaults():
    filepath = getSettingsFile()
    fp = safeOpen(filepath, "r", False, False, False)
    if fp:
        loadSettingsFile(fp, filepath, None)
        fp.close()


def clearSettings(scn):
    from sys import platform
    folder = os.path.dirname(__file__)
    if bpy.app.version < (2,80,0):
        file = "factory-settings-27x.json"
    else:
        file = "factory-settings-28x.json"
    filepath = os.path.join(folder, "data", file)
    fp = safeOpen(filepath, "r", True, True, True)
    if fp:
        loadSettingsFile(fp, filepath, scn)
        fp.close()
    scn.DazPath1, scn.DazPath2, scn.DazPath3, scn.DazErrorPath = getDefaultPaths()
    scn.DazCaseSensitivePaths = (platform != 'win32')


def loadSettingsFile(fp, filepath, scn):
    import json
    if fp:
        struct = json.load(fp)
    else:
        return
    print("Load settings from", filepath)

    if "daz-settings" not in struct.keys():
        msg = ("Not a settings file   :\n'%s'" % filepath)
        if scn:
            raise DazError(msg)
        else:
            print(msg)
            return

    corrupt = False
    try:
        loadLines(struct["daz-settings"], scn)
    except:
        corrupt = True
    finally:
        fp.close()
    if corrupt:
        msg = ("%s is corrupt. Please resave" % filepath)
        if scn:
            raise DazError(msg)
        else:
            print(msg)
    else:
        print("Settings loaded")


def getPropType(struct, value):
    if "items" in struct.keys():
        if "default" in struct.keys():
            return "EnumProperty"
        else:
            return None
    elif isinstance(value, bool):
        return "BoolProperty"
    elif isinstance(value, int):
        return "IntProperty"
    elif isinstance(value, float):
        return "FloatProperty"
    elif isinstance(value, str):
        return "StringProperty"
    else:
        return None


class DAZ_OT_LoadFactorySettings(bpy.types.Operator):
    bl_idname = "daz.load_factory_settings"
    bl_label = "Load Factory Settings"
    bl_options = {'UNDO'}

    def execute(self, context):
        try:
            clearSettings(context.scene)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}


class DAZ_OT_LoadDefaultSettings(bpy.types.Operator):
    bl_idname = "daz.load_default_settings"
    bl_label = "Load Default Settings"
    bl_options = {'UNDO'}

    def execute(self, context):
        try:
            filepath = getSettingsFile()
            loadSettings(filepath, context.scene)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}


class DAZ_OT_LoadSettingsFile(bpy.types.Operator, SingleFile, JsonFile):
    bl_idname = "daz.load_settings_file"
    bl_label = "Load Settings File"
    bl_description = "Load settings from file"
    bl_options = {'UNDO'}

    def execute(self, context):
        try:
            loadSettings(self.filepath, context.scene)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}


    def invoke(self, context, event):
        self.properties.filepath = os.path.dirname(getSettingsFile()) + "/"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

classes = [
    DAZ_OT_LoadFactorySettings,
    DAZ_OT_SaveDefaultSettings,
    DAZ_OT_LoadDefaultSettings,
    DAZ_OT_SaveSettingsFile,
    DAZ_OT_LoadSettingsFile,
]

def getDefaultPaths():
    path1 = os.path.join(getMyDocuments(), "DAZ 3D", "Studio", "My Library")
    path2 = "C:/Users/Public/Documents/My DAZ 3D Library"
    path3 = "C:/Program Files/DAZ 3D/DAZStudio4/shaders/iray"
    errorpath = os.path.join(getMyDocuments(), "daz_importer_errors.txt")
    return path1, path2, path3, errorpath


def initialize():
    path1, path2, path3, errorpath = getDefaultPaths()

    bpy.types.Scene.DazNumPaths = IntProperty(
        name = "Number Of DAZ Paths",
        description = "The number of DAZ library paths",
        min=1, max = 9,
        default = 4)

    bpy.types.Scene.DazPath1 = StringProperty(
        name = "DAZ Path 1",
        description = "Primary search path for DAZ Studio assets",
        default = path1)

    bpy.types.Scene.DazPath2 = StringProperty(
        name = "DAZ Path 2",
        description = "Secondary search path for DAZ Studio assets",
        default = path2)

    bpy.types.Scene.DazPath3 = StringProperty(
        name = "DAZ Path 3",
        description = "Third search path for DAZ Studio assets",
        default = path3)

    for n in range(4, 10):
        setattr(bpy.types.Scene, "DazPath%d" % n,
            StringProperty(
                name = "DAZ Path %d" % n,
                description = "Additional search path for DAZ Studio assets",
                default = ""))

    bpy.types.Scene.DazErrorPath = StringProperty(
        name = "Error Path",
        description = "Path to error report file",
        default = errorpath)

    bpy.types.Scene.DazVerbosity = IntProperty(
        name = "Verbosity",
        description = "Controls the number of warning messages when loading files",
        min=1, max = 5,
        default = 2)

    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)

