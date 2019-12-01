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
import bpy
from bpy.props import *
from bpy_extras.io_utils import ImportHelper
from mathutils import Vector
from .error import *
from .utils import *
from . import utils
from .settings import theSettings
if bpy.app.version < (2,80,0):
    from .buttons27 import DazImageFile, MultiFile, MorphStrings, PoseStrings, PrefixString, TypeString, ValueBool, KeyString, CatGroupString, CatGroupString, ActionString, TypePrefixCat, UseOpenBool, DatFile, SingleFile, DazCustomGroup, DazCategory, MorphTypes
else:
    from .buttons28 import DazImageFile, MultiFile, MorphStrings, PoseStrings, PrefixString, TypeString, ValueBool, KeyString, CatGroupString, CatGroupString, ActionString, TypePrefixCat, UseOpenBool, DatFile, SingleFile, DazCustomGroup, DazCategory, MorphTypes

#------------------------------------------------------------------
#   Global lists of morph paths
#------------------------------------------------------------------

ShortForms = {
    "phmunits" : ["phmbrow", "phmcheek", "phmeye", "phmjaw", "phmlip", "phmmouth", "phmnos", "phmteeth", "phmtongue"],

    "ectrlunits" : ["ectrlbrow", "ectrlcheek", "ectrleye", "ectrljaw", "ectrllip", "ectrlmouth", "ectrlnos", "ectrlteeth", "ectrltongue"],

    "ctrlhands" : ["ctrllfinger", "ctrllhand", "ctrllthumb", "ctrllindex", "ctrllmid", "ctrllring", "ctrllpinky",
             "ctrlrfinger", "ctrlrhand", "ctrlrthumb", "ctrlrindex", "ctrlrmid", "ctrlrring", "ctrlrpinky"],

    "ctrltoes" : ["ctrllindextoe", "ctrllmidtoe", "ctrllringtoe", "ctrllpinkytoe",
            "ctrlrindextoe", "ctrlrmidtoe", "ctrlrringtoe", "ctrlrpinkytoe"],

    "pctrlhands" : ["pctrllfinger", "pctrllhand", "pctrllthumb", "pctrllindex", "pctrllmid", "pctrllring", "pctrllpinky",
             "pctrlrfinger", "pctrlrhand", "pctrlrthumb", "pctrlrindex", "pctrlrmid", "pctrlrring", "pctrlrpinky"],

    "pctrltoes" : ["pctrllindextoe", "pctrllmidtoe", "pctrllringtoe", "pctrllpinkytoe",
            "pctrlrindextoe", "pctrlrmidtoe", "pctrlrringtoe", "pctrlrpinkytoe"],
}
ShortForms["units"] = ShortForms["ectrlunits"] + ShortForms["phmunits"]

def getShortformList(item):
    if isinstance(item, list):
        return item
    else:
        return ShortForms[item]


theMorphFiles = {}
theMorphNames = {}
theMorphOptions = {}

def setupMorphPaths(scn, force):
    global theMorphFiles, theMorphNames, theMorphOptions
    from collections import OrderedDict
    from .asset import getDazPaths, fixBrokenPath
    from .load_json import loadJson

    if theMorphFiles and not force:
        return
    theMorphFiles = {}
    theMorphNames = {}

    folder = os.path.join(os.path.dirname(__file__), "data/paths/")
    charPaths = {}
    for file in os.listdir(folder):
        path = os.path.join(folder, file)
        struct = loadJson(path)
        charPaths[struct["name"]] = struct

    for char in charPaths.keys():
        charFiles = theMorphFiles[char] = {}

        for key,struct in charPaths[char].items():
            if key in ["name", "hd-morphs"]:
                continue
            type = key.capitalize()
            if type not in charFiles.keys():
                charFiles[type] = OrderedDict()
            typeFiles = charFiles[type]
            if type not in theMorphNames.keys():
                theMorphNames[type] = OrderedDict()
            typeNames = theMorphNames[type]

            if isinstance(struct["prefix"], list):
                prefixes = struct["prefix"]
            else:
                prefixes = [struct["prefix"]]
            folder = struct["path"]
            includes = getShortformList(struct["include"])
            excludes = getShortformList(struct["exclude"])
            if "exclude2" in struct.keys():
                excludes += getShortformList(struct["exclude2"])

            for dazpath in getDazPaths(scn):
                folderpath = os.path.join(dazpath, folder)
                if not os.path.exists(folderpath):
                    folderpath = fixBrokenPath(folderpath)
                if os.path.exists(folderpath):
                    for file in os.listdir(folderpath):
                        fname,ext = os.path.splitext(file)
                        if ext not in [".duf", ".dsf"]:
                            continue
                        isright,name = isRightType(fname, prefixes, includes, excludes)
                        if isright:
                            fpath = os.path.join(folder, file)
                            typeFiles[name] = os.path.join(folderpath, file)
                            prop = BoolProperty(name=name, default=True)
                            setattr(bpy.types.Scene, "Daz"+name, prop)
                            typeNames[fname.lower()] = name


def isRightType(fname, prefixes, includes, excludes):
    string = fname.lower()
    ok = False
    for prefix in prefixes:
        n = len(prefix)
        if string[0:n] == prefix:
            ok = True
            name = fname[n:]
            break
    if not ok:
        return False, fname

    if includes == []:
        for exclude in excludes:
            if exclude in string:
                return False, name
        return True, name

    for include in includes:
        if (include in string or
            string[0:len(include)-1] == include[1:]):
            for exclude in excludes:
                if (exclude in string or
                    string[0:len(exclude)-1] == exclude[1:]):
                    return False, name
            return True, name
    return False, name


class DAZ_OT_Update(bpy.types.Operator):
    bl_idname = "daz.update_morph_paths"
    bl_label = "Update Morph Paths"
    bl_description = "Update paths to predefined morphs"
    bl_options = {'UNDO'}

    def execute(self, context):
        setupMorphPaths(context.scene, True)
        return{'FINISHED'}


class DAZ_OT_SelectAll(bpy.types.Operator, TypeString, ValueBool):
    bl_idname = "daz.select_all_morphs"
    bl_label = "Select All"
    bl_description = "Select/Deselect all morphs in this section"
    bl_options = {'UNDO'}

    def execute(self, context):
        scn = context.scene
        names = theMorphNames[self.type]
        for name in names.values():
            scn["Daz"+name] = self.value
        return{'FINISHED'}

#------------------------------------------------------------------
#   Favorites
#------------------------------------------------------------------

def saveFavorites(context):
    from .finger import getFingeredCharacter
    from .fileutils import safeOpen
    rig,_mesh,char = getFingeredCharacter(context.object)
    scn = context.scene
    favlist = []
    if char in theMorphFiles.keys():
        for type in ["Units", "Expressions", "Visemes", "Correctives"]:
            for name in theMorphFiles[char][type].keys():
                if (hasattr(scn, "Daz"+name) and
                    getattr(scn, "Daz"+name)):
                    favlist.append(name)

    folder = os.path.join(os.path.dirname(__file__), "data", "favorites")
    if not os.path.exists(folder):
        os.makedirs(folder)
    filepath = os.path.join(folder, utils.tolower(rig.DazMesh)+".txt")
    with safeOpen(filepath, "w") as fp:
        fp.write("\n".join(favlist))
    print("Favorites saved to", filepath)


class DAZ_OT_SaveFavorites(bpy.types.Operator):
    bl_idname = "daz.save_favorite_morphs"
    bl_label = "Save Favorites"
    bl_description = "Save favorite morphs"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.DazId)

    def execute(self, context):
        try:
            saveFavorites(context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}


def loadFavorites(context):
    from .finger import getFingeredCharacter
    from .fileutils import safeOpen
    rig,_mesh,char = getFingeredCharacter(context.object)
    folder = os.path.join(os.path.dirname(__file__), "data", "favorites")
    favlist = []
    if os.path.exists(folder):
        filepath = os.path.join(folder, utils.tolower(rig.DazMesh)+".txt")
        if os.path.exists(filepath):
            with safeOpen(filepath, "rU") as fp:
                favlist = [line.split()[0] for line in fp]
    if favlist == []:
        print("No favorites found for", rig.DazMesh)
        return

    scn = context.scene
    if char in theMorphFiles.keys():
        for type in ["Units", "Expressions", "Visemes", "Correctives"]:
            for name in theMorphFiles[char][type].keys():
                if hasattr(scn, "Daz"+name):
                    setattr(scn, "Daz"+name, (name in favlist))
    print("Favorites loaded from", filepath)


class DAZ_OT_LoadFavorites(bpy.types.Operator):
    bl_idname = "daz.load_favorite_morphs"
    bl_label = "Load Favorites"
    bl_description = "Load favorite morphs"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.DazId)

    def execute(self, context):
        try:
            loadFavorites(context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}

#------------------------------------------------------------------
#   LoadMorph base class
#------------------------------------------------------------------

theLimitationsMessage = (
'''
Not all morphs were loaded correctly
due to Blender limitations.
See console for details.
''')

class LoadMorph:

    useSoftLimits = True
    useShapekeysOnly = False
    useShapekeys = True
    useDrivers = True
    suppressError = False

    def __init__(self, mesh=None, rig=None):
        self.mesh = mesh
        self.rig = rig


    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.DazId)


    def getObject(self):
        if self.rig:
            return self.rig
        elif self.mesh:
            return self.mesh


    def getSingleMorph(self, filepath, scn):
        from .modifier import Morph, FormulaAsset
        from .readfile import readDufFile
        from .files import parseAssetFile
        from .driver import makeShapekeyDriver

        ob = self.getObject()
        if ob is None:
            return []

        struct = readDufFile(filepath)
        asset = parseAssetFile(struct)
        props = []
        if asset is None:
            if theSettings.verbosity > 1:
                msg = ("Not a morph asset:\n  '%s'" % filepath)
                if self.suppressError:
                    print(msg)
                else:
                    raise DazError(msg)
            return []

        skey = None
        prop = None
        if self.useShapekeys and isinstance(asset, Morph) and self.mesh and self.mesh.type == 'MESH':
            if asset.vertex_count != len(self.mesh.data.vertices):
                if theSettings.verbosity > 2:
                    msg = ("Vertex count mismatch:\n  %d != %d" % (asset.vertex_count, len(self.mesh.data.vertices)))
                    if self.suppressError:
                        print(msg)
                    else:
                        raise DazError(msg)
                return []
            asset.buildMorph(self.mesh, ob.DazCharacterScale, self.useSoftLimits)
            skey,ob,sname = asset.rna
            if self.rig and theSettings.useDrivers:
                prop = propFromName(sname, self.type, self.prefix, self.rig)
                skey.name = prop
                min = skey.slider_min if theSettings.useDazPropLimits else None
                max = skey.slider_max if theSettings.useDazPropLimits else None
                makeShapekeyDriver(ob, prop, skey.value, self.rig, prop, min=min, max=max)
                props = [prop]

        if (self.useDrivers and
            isinstance(asset, FormulaAsset) and
            asset.formulas and
            self.rig):
            from .formula import buildShapeFormula, buildPropFormula
            if not self.useShapekeysOnly:
                props = buildPropFormula(asset, scn, self.rig, self.type, self.prefix, self.errors)
                props = list(props)
            if self.useShapekeys:
                success = buildShapeFormula(asset, scn, self.rig, self.mesh)
                if self.useShapekeysOnly and not success and skey:
                    print("Could not build shape formula", skey.name)

        if props:
            return props
        elif skey:
            return [skey.name]
        else:
            return []


def propFromName(key, type, prefix, rig):
    if prefix:
        names = theMorphNames[type]
        name = nameFromKey(key, names, rig)
        if name:
            prop = prefix+name
            return prop
    return key


class LoadShapekey(LoadMorph):

    useDrivers = False



#------------------------------------------------------------------
#   Load typed morphs base class
#------------------------------------------------------------------

class LoadAllMorphs(LoadMorph):

    suppressError = True

    def execute(self, context):
        try:
            self.loadAllMorphs(context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}


    def loadAllMorphs(self, context):
        import time
        from .main import finishMain
        from .finger import getFingeredCharacter

        scn = context.scene
        setupMorphPaths(scn, False)
        addDrivers = (scn.DazAddFaceDrivers and not self.useShapekeysOnly)

        self.rig, self.mesh, char = getFingeredCharacter(context.object)
        if self.mesh is None:
            if self.useShapekeysOnly:
                raise DazError("No mesh found")
            elif self.rig.DazRig == "genesis3":
                char = "Genesis3-female"
                self.mesh = self.rig
                addDrivers = True
            elif self.rig.DazRig == "genesis8":
                char = "Genesis8-female"
                self.mesh = self.rig
                addDrivers = True
            else:
                print("Can not add morphs to this mesh: %s" % self.rig.DazRig)
                return

        self.rig["Daz"+self.type] = char
        self.mesh["Daz"+self.type] = char
        self.rig.DazNewStyleExpressions = True

        try:
            files = theMorphFiles[char][self.type]
        except KeyError:
            files = []
        if not files:
            raise DazError("No morph files:\nCharacter: %s\nMorph type: %s" % (char, self.type))

        theSettings.forMorphLoad(self.mesh, scn, addDrivers)
        self.errors = {}
        t1 = time.clock()
        print("\n--------------------\n%s" % self.type)
        snames = []
        for name,filepath in files.items():
            if hasattr(scn, "Daz"+name) and getattr(scn, "Daz"+name):
                print("*", name)
                snames += self.getSingleMorph(filepath, scn)
            else:
                print("-", name)
        updateDrivers(self.mesh)
        updateDrivers(self.rig)
        finishMain(filepath, t1)
        if self.errors:
            print("but there were errors:")
            for err,struct in self.errors.items():
                print("%s:" % err)
                print("  Props: %s" % struct["props"])
                print("  Bones: %s" % struct["bones"])


class DAZ_OT_LoadAllUnits(bpy.types.Operator, LoadAllMorphs):
    bl_idname = "daz.load_all_units"
    bl_label = "Load Face Units"
    bl_description = "Load all face unit morphs"
    bl_options = {'UNDO'}

    type = "Units"
    prefix = "DzU"


class DAZ_OT_LoadAllExpressions(bpy.types.Operator, LoadAllMorphs):
    bl_idname = "daz.load_all_expressions"
    bl_label = "Load Expressions"
    bl_description = "Load all expression morphs"
    bl_options = {'UNDO'}

    type = "Expressions"
    prefix = "DzE"


class DAZ_OT_LoadAllVisemes(bpy.types.Operator, LoadAllMorphs):
    bl_idname = "daz.load_all_visemes"
    bl_label = "Load Visemes"
    bl_description = "Load all viseme morphs"
    bl_options = {'UNDO'}

    type = "Visemes"
    prefix = "DzV"


class DAZ_OT_LoadAllCorrectives(bpy.types.Operator, LoadAllMorphs):
    bl_idname = "daz.load_all_correctives"
    bl_label = "Load Correctives"
    bl_description = "Load all corrective morphs"
    bl_options = {'UNDO'}

    type = "Correctives"
    prefix = "DzC"
    useShapekeysOnly = True
    useSoftLimits = False

#------------------------------------------------------------------------
#   Import general morph or driven pose
#------------------------------------------------------------------------

class DAZ_OT_ImportMorph(bpy.types.Operator, LoadMorph, DazImageFile, MultiFile, MorphStrings):
    bl_idname = "daz.import_morph"
    bl_label = "Import Morph(s)"
    bl_description = "Import morph(s) from native DAZ file(s) (*.duf, *.dsf)"
    bl_options = {'UNDO'}

    type = "Shapes"
    prefix = ""
    custom = "DazCustomMorphs"
    catgroup = "DazMorphCats"

    def draw(self, context):
        self.layout.prop(self, "useDrivers")
        self.layout.prop(self, "catname")


    def execute(self, context):
        try:
            self.importMorphs(context.scene)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}


    def invoke(self, context, event):
        from .fileutils import getFolder
        from .finger import getFingeredCharacter
        self.rig, self.mesh, char = getFingeredCharacter(context.object)
        folder = getFolder(self.mesh, context.scene, ["Morphs/", ""])
        if folder is not None:
            self.properties.filepath = folder
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


    def importMorphs(self, scn):
        from .driver import setBoolProp
        snames = self.getMorphs(self.filepath, scn)
        addToCategories(self.rig, snames, self.catname, self.catgroup)
        if self.rig:
            setBoolProp(self.rig, self.custom, True)
        if self.mesh:
            setBoolProp(self.mesh, self.custom, True)
        if self.errors:
            raise DazError(theLimitationsMessage)


    def getMorphs(self, filepath, scn):
        import time
        from .asset import clearAssets
        from .main import finishMain
        from .fileutils import getMultiFiles

        if self.mesh:
            ob = self.mesh
        elif self.rig:
            ob = self.rig
        else:
            raise DazError("Neither mesh nor rig selected")
        theSettings.forMorphLoad(ob, scn, self.useDrivers)

        self.errors = {}
        t1 = time.clock()
        print("\n--------------------")
        snames = []
        paths = getMultiFiles(self, ["duf", "dsf"])
        self.suppressError = (len(paths) > 1)
        for path in paths:
            file = os.path.basename(path)
            names = self.getSingleMorph(path, scn)
            if names:
                print("*", file)
                snames += names
            else:
                print("-", file)
        updateDrivers(self.rig)
        updateDrivers(self.mesh)
        finishMain(filepath, t1)
        if self.errors:
            print("but there were errors:")
            for err,struct in self.errors.items():
                print("%s:" % err)
                print("  Props: %s" % struct["props"])
                print("  Bones: %s" % struct["bones"])

        return snames

#------------------------------------------------------------------------
#   Categories
#------------------------------------------------------------------------

def addToCategories(rig, snames, catname, catgroup="DazMorphCats"):
    from .driver import setBoolProp
    if snames and rig is not None:
        categories = getattr(rig, catgroup)
        cats = dict([(cat.name,cat) for cat in categories])
        if catname not in cats.keys():
            cat = categories.add()
            cat.name = catname
        else:
            cat = cats[catname]
        setBoolProp(rig, "DazShow"+catname, True)

        morphs = dict([(morph.prop,morph) for morph in cat.morphs])
        for sname in snames:
            if sname not in morphs.keys():
                morph = cat.morphs.add()
            else:
                morph = morphs[sname]

            morph.prop = sname
            if sname[0:4].lower() == "ctrl":
                morph.name = sname[4:]
            elif sname[1:5].lower() == "ctrl":
                morph.name = sname[5:]
            else:
                morph.name = sname

#------------------------------------------------------------------------
#   Rename category
#------------------------------------------------------------------------

def getOpenAttr(catgroup):
    return ("%sOpen" % catgroup)


class ChangeCategory(CatGroupString):
    def execute(self, context):
        try:
            rig = context.object
            scn = context.scene
            categories = getattr(rig, self.catgroup)
            catname = getattr(scn, "%sContent" % self.catgroup)
            key = ("DazShow%s" % catname)
            self.doChange(rig, scn, categories, catname, key)
        except DazError:
            handleDazError(context)
        finally:
            attr = getOpenAttr(self.catgroup)
            setattr(context.scene, attr, False)
        return {'FINISHED'}


class DAZ_OT_RenameCategoryOK(bpy.types.Operator, ChangeCategory):
    bl_idname = "daz.rename_category"
    bl_label = "Rename Category"
    bl_description = "Rename selected category"
    bl_options = {'UNDO'}

    def doChange(self, rig, scn, categories, catname, key):
        from .driver import setBoolProp
        cat = categories[catname]
        cat.name = scn.DazNewCatName
        if key in rig.keys():
            show = rig[key]
            del rig[key]
        else:
            show = True
        setBoolProp(rig, "DazShow%s" % cat.name, show)


class DAZ_OT_RemoveCategoryOK(bpy.types.Operator, ChangeCategory):
    bl_idname = "daz.remove_category"
    bl_label = "Remove Category"
    bl_description = "Remove selected category and associated drivers"
    bl_options = {'UNDO'}

    def doChange(self, rig, scn, categories, catname, key):
        from .driver import removePropDrivers
        from .daz import removeFromPropGroup
        #if len(cat.morphs) > 0:
        #    raise DazError("Cannot remove non-empty category:      \n%s" % cat.name)
        cat = categories[catname]
        for grp in cat.morphs:
            if grp.prop in rig.keys():
                rig[grp.prop] = 0.0
            path = ('["%s"]' % grp.prop)
            keep = removePropDrivers(rig, path, rig)
            for ob in rig.children:
                if ob.type == 'MESH':
                    if removePropDrivers(ob.data.shape_keys, path, rig):
                        keep = True
            if grp.prop in rig.keys():
                for pb in rig.pose.bones:
                    removeFromPropGroup(pb.DazLocProps, grp.prop)
                    removeFromPropGroup(pb.DazRotProps, grp.prop)
                    removeFromPropGroup(pb.DazScaleProps, grp.prop)
                if not keep:
                    del rig[grp.prop]
        for n,catn in enumerate(categories):
            if cat == catn:
                categories.remove(n)
                break
        if key in ob.keys():
            del ob[key]


class DAZ_OT_ChangeCategoryCancel(bpy.types.Operator, CatGroupString):
    bl_idname = "daz.change_category_cancel"
    bl_label = "Cancel"
    bl_description = "Cancel category change"
    bl_options = {'UNDO'}

    def execute(self, context):
        attr = getOpenAttr(self.catgroup)
        setattr(context.scene, attr, False)
        return {'FINISHED'}


class DAZ_OT_ChangeCategory(bpy.types.Operator, CatGroupString, ActionString):
    bl_idname = "daz.change_category"
    bl_label = "Change Category"
    bl_description = "Rename or remove category"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE')

    def execute(self, context):
        ob = context.object
        scn = context.scene
        categories = getattr(ob, self.catgroup)
        enums = EnumProperty(
            items = [(cat.name, cat.name, cat.name) for cat in categories],
            name = self.catgroup[3:-4])
        setattr(bpy.types.Scene, "%sContent" % self.catgroup, enums)

        attr = getOpenAttr(self.catgroup)
        setattr(context.scene, attr, True)
        return {'FINISHED'}

#------------------------------------------------------------------------
#   Apply morphs
#------------------------------------------------------------------------

def getShapeKeyCoords(ob):
    coords = [v.co for v in ob.data.vertices]
    skeys = []
    if ob.data.shape_keys:
        for skey in ob.data.shape_keys.key_blocks[1:]:
            if abs(skey.value) > 1e-4:
                coords = [co + skey.value*(skey.data[n].co - ob.data.vertices[n].co) for n,co in enumerate(coords)]
            skeys.append(skey)
    return skeys,coords


def applyMorphs(rig, props):
    for ob in rig.children:
        basic = ob.data.shape_keys.key_blocks[0]
        skeys,coords = getShapeKeyCoords(ob)
        for skey in skeys:
            path = 'key_blocks["%s"].value' % skey.name
            getDrivingProps(ob.data.shape_keys, path, props)
            ob.shape_key_remove(skey)
        basic = ob.data.shape_keys.key_blocks[0]
        ob.shape_key_remove(basic)
        for vn,co in enumerate(coords):
            ob.data.vertices[vn].co = co
    print("Morphs applied")


def getDrivingProps(rna, channel, props):
    if rna.animation_data:
        for fcu in rna.animation_data.drivers:
            for var in fcu.driver.variables:
                for trg in var.targets:
                    prop = trg.data_path.split('"')[1]
                    props[prop] = trg.id


def removeDrivingProps(rig, props):
    for prop,id in props.items():
        if rig == id:
            del rig[prop]

    for cat in rig.DazCategories:
        showname = "DazShow" + cat.name
        if hasattr(rig, showname):
            delattr(rig, showname)
        rig.DazCategories.remove(cat)

#------------------------------------------------------------------------
#   Select and unselect all
#------------------------------------------------------------------------

class Activator(PrefixString, TypeString, CatGroupString):
    def execute(self, context):
        from .driver import setBoolProp
        rig = getRigFromObject(context.object)
        keys = getRelevantMorphs(rig, self.type, self.prefix, self.catgroup)
        if self.type == "CUSTOM":
            for key in keys:
                setBoolProp(rig, "DzA"+key.prop, self.activate)
        else:
            for key in keys:
                setBoolProp(rig, "DzA"+key, self.activate)
        return{'FINISHED'}


class DAZ_OT_ActivateAll(bpy.types.Operator, Activator):
    bl_idname = "daz.activate_all"
    bl_label = "Select All"
    bl_description = "Select all morphs of this type"
    bl_options = {'UNDO'}

    activate = True


class DAZ_OT_DeactivateAll(bpy.types.Operator, Activator):
    bl_idname = "daz.deactivate_all"
    bl_label = "Unselect All"
    bl_description = "Unselect all morphs of this type"
    bl_options = {'UNDO'}

    activate = False

#------------------------------------------------------------------------
#   Prettifying
#------------------------------------------------------------------------

def prettifyAll(context):
    scn = context.scene
    for ob in getSceneObjects(context):
        if ob.type == 'ARMATURE':
            for prop in ob.keys():
                if prop[0:7] == "DazShow":
                    setattr(bpy.types.Object, prop, BoolProperty(default=True))
                elif prop[0:3] in ["DzA", "Mhh", "DzM"]:
                    setattr(bpy.types.Object, prop, BoolProperty(default=True))                            


class DAZ_OT_Prettify(bpy.types.Operator):
    bl_idname = "daz.prettify"
    bl_label = "Prettify Panels"
    bl_description = (
        "Change sliders to checkboxes\n" +
        "(If boolean options appear as sliders, use this button to refresh them)"
        )
    bl_options = {'UNDO'}

    def execute(self, context):
        prettifyAll(context)
        return{'FINISHED'}

#------------------------------------------------------------------
#   Update scene
#------------------------------------------------------------------

class DAZ_OT_ForceUpdate(bpy.types.Operator):
    bl_idname = "daz.force_update"
    bl_label = "Update"
    bl_description = "Force all morphs to update"
    bl_options = {'UNDO'}

    def execute(self, context):
        updateScene(context)
        rig = getRigFromObject(context.object)
        updateRig(rig, context)
        updateDrivers(context.object)
        return {'FINISHED'}

#------------------------------------------------------------------
#   Clear morphs
#------------------------------------------------------------------

def getRelevantMorphs(rig, type, prefix, catgroup):
    morphs = []
    if rig is None:
        return morphs
    if type == "CUSTOM":
        for cat in getattr(rig, catgroup):
            morphs += cat.morphs
    elif rig.DazNewStyleExpressions:
        for key in rig.keys():
            if key[0:3] == prefix:
                morphs.append(key)
    else:
        names = theMorphNames[type]
        for key in rig.keys():
            name = nameFromKey(key, names, rig)
            if name and isinstance(rig[key], float):
                morphs.append(key)
    return morphs


def clearMorphs(rig, type, prefix, catgroup, scn, frame, force):
    keys = getRelevantMorphs(rig, type, prefix, catgroup)

    if type == "CUSTOM":
        for key in keys:
            if isActive(rig, key.prop, force) and not rig[key.prop] == 0.0:
                rig[key.prop] = 0.0
                autoKeyProp(rig, key.prop, scn, frame, force)
    else:
        for key in keys:
            if isActive(rig, key, force) and not rig[key] == 0.0:
                rig[key] = 0.0
                autoKeyProp(rig, key, scn, frame, force)


def updateMorphs(rig, type, prefix, catgroup, scn, frame, force):
    keys = getRelevantMorphs(rig, type, prefix, catgroup)
    for key in keys:
        if isActive(rig, key):
            autoKeyProp(rig, key, scn, frame, force)


def nameFromKey(key, names, rig):
    key = key.lower()
    if rig.DazRig == "genesis8":
        keyhd = key + "_hd"
        if keyhd in names.keys():
            return names[keyhd]
        elif "e"+keyhd in names.keys():
            return names["e"+keyhd]
    if key in names.keys():
        return names[key]
    elif "e"+key in names.keys():
        return names["e"+key]
    else:
        for end1,end2 in [("in-out", "out-in")]:
            n = len(end1)
            for prefix in ["e", ""]:
                stem = prefix+key[:-n]
                if key[-n:] == end1 and stem+end2 in names.keys():
                    return names[stem+end2]
                elif key[-n:] == end2 and stem+end1 in names.keys():
                    return names[stem+end1]
    return None


class DAZ_OT_ClearMorphs(bpy.types.Operator, TypePrefixCat):
    bl_idname = "daz.clear_morphs"
    bl_label = "Clear"
    bl_description = "Set all morphs of specified type to zero"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object)

    def execute(self, context):
        try:
            rig = getRigFromObject(context.object)
            if rig:
                scn = context.scene
                clearMorphs(rig, self.type, self.prefix, self.catgroup, scn, scn.frame_current, False)
                updateRig(rig, context)
                if scn.tool_settings.use_keyframe_insert_auto:
                    updateScene(context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}



class DAZ_OT_UpdateMorphs(bpy.types.Operator, KeyString, TypePrefixCat):
    bl_idname = "daz.update_morphs"
    bl_label = "Update"
    bl_description = "Set keys at current frame for all props of specified type with keys"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type in ['MESH', 'ARMATURE'])

    def execute(self, context):
        try:
            rig = getRigFromObject(context.object)
            if rig:
                scn = context.scene
                updateMorphs(rig, self.type, self.prefix, self.catgroup, scn, scn.frame_current)
                updateScene(context)
                updateRig(rig, context)
        except DazError:
            handleDazError(context)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}

#------------------------------------------------------------------
#   Add morphs to keyset
#------------------------------------------------------------------

def addKeySet(rig, type, prefix, catgroup, scn, frame):
    if rig is None:
        return
    aksi = scn.keying_sets.active_index
    if aksi <= -1:
        aks = scn.keying_sets.new(idname = "daz_morphs", name = "daz_morphs")
    aks = scn.keying_sets.active
    if type == "CUSTOM":
        for cat in getattr(rig, catgroup):
            for morph in cat.morphs:
                path = "[" + '"' + morph.prop + '"' + "]"
                aks.paths.add(rig.id_data, path)
    elif rig.DazNewStyleExpressions:
        for key in rig.keys():
            if key[0:3] == prefix:
                path = "[" + '"' + key + '"' + "]"
                aks.paths.add(rig.id_data, path)
    else:
        names = theMorphNames[type]
        for key in rig.keys():
            name = nameFromKey(key, names, rig)
            if name and isinstance(rig[key], float):
                path = "[" + '"' + key + '"' + "]"
                aks.paths.add(rig.id_data, path)


class DAZ_OT_AddKeysets(bpy.types.Operator, TypePrefixCat):
    bl_idname = "daz.add_keyset"
    bl_label = "Keyset"
    bl_description = "Add category morphs to active custom keying set, or make new one"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object)

    def execute(self, context):
        from .finger import getFingeredCharacter
        try:
            rig = getRigFromObject(context.object)
            if rig:
                scn = context.scene
                addKeySet(rig, self.type, self.prefix, self.catgroup, scn, scn.frame_current)
                updateScene(context)
                updateRig(rig, context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}

#------------------------------------------------------------------
#   Set morph keys
#------------------------------------------------------------------

def keyMorphs(rig, type, prefix, catgroup, scn, frame):
    if rig is None:
        return
    if type == "CUSTOM":
        for cat in getattr(rig, catgroup):
            for morph in cat.morphs:
                if morph.prop in rig.keys() and isActive(rig, morph.prop):
                    keyProp(rig, morph.prop, frame)
    elif rig.DazNewStyleExpressions:
        for key in rig.keys():
            if key[0:3] == prefix and isActive(rig, key):
                keyProp(rig, key, frame)
    else:
        names = theMorphNames[type]
        for key in rig.keys():
            name = nameFromKey(key, names, rig)
            if name and isinstance(rig[key], float):
                keyProp(rig, key, frame)


class DAZ_OT_KeyMorphs(bpy.types.Operator, TypePrefixCat):
    bl_idname = "daz.key_morphs"
    bl_label = "Set Keys"
    bl_description = "Set keys for all morphs of specified type at current frame"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object)

    def execute(self, context):
        try:
            rig = getRigFromObject(context.object)
            if rig:
                scn = context.scene
                keyMorphs(rig, self.type, self.prefix, self.catgroup, scn, scn.frame_current)
                updateScene(context)
                updateRig(rig, context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}

#------------------------------------------------------------------
#   Remove morph keys
#------------------------------------------------------------------

def unkeyMorphs(rig, type, prefix, catgroup, scn, frame):
    if rig is None:
        return
    if type == "CUSTOM":
        for cat in getattr(rig, catgroup):
            for morph in cat.morphs:
                if morph.prop in rig.keys() and isActive(rig, morph.prop):
                    unkeyProp(rig, morph.prop, frame)
    elif rig.DazNewStyleExpressions:
        for key in rig.keys():
            if key[0:3] == prefix and isActive(rig, key):
                unkeyProp(rig, key, frame)
    else:
        names = theMorphNames[type]
        for key in rig.keys():
            name = nameFromKey(key, names, rig)
            if name and isinstance(rig[key], float):
                unkeyProp(rig, key, frame)


class DAZ_OT_UnkeyMorphs(bpy.types.Operator, TypePrefixCat):
    bl_idname = "daz.unkey_morphs"
    bl_label = "Remove Keys"
    bl_description = "Remove keys from all morphs of specified type at current frame"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object)

    def execute(self, context):
        try:
            rig = getRigFromObject(context.object)
            if rig:
                scn = context.scene
                unkeyMorphs(rig, self.type, self.prefix, self.catgroup, scn, scn.frame_current)
                updateScene(context)
                updateRig(rig, context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}

#------------------------------------------------------------------
#   Update property limits
#------------------------------------------------------------------

def getCustomProps(ob):
    props = []
    for catgroup in ["DazMorphCats", "DazPoseCats"]:
        for cat in getattr(ob, catgroup):
            props += [morph.prop for morph in cat.morphs]
    return props


def updatePropLimits(rig, context):
    from .driver import getShapekeyBoneDriver, setFloatProp
    scn = context.scene
    min = scn.DazPropMin
    max = scn.DazPropMax
    props = getCustomProps(rig)
    for ob in rig.children:
        if ob.type == 'MESH' and ob.data.shape_keys:
            for skey in ob.data.shape_keys.key_blocks:
                if skey.name in props or skey.name[0:2] == "Dz":
                    skey.slider_min = min
                    skey.slider_max = max

    for prop in rig.keys():
        if (prop in props or 
            (prop[0:2] == "Dz" and prop[0:3] != "DzA")):
            setFloatProp(rig, prop, rig[prop], min, max)
    updateScene(context)
    updateRig(rig, context)
    print("Property limits updated")


class DAZ_OT_UpdatePropLimits(bpy.types.Operator):
    bl_idname = "daz.update_prop_limits"
    bl_label = "Update Property Limits"
    bl_description = "Update min and max value for properties"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return context.object

    def execute(self, context):
        try:
            rig = getRigFromObject(context.object)
            if rig:
                updatePropLimits(rig, context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}

#------------------------------------------------------------------
#   Remove morphs
#------------------------------------------------------------------

def removeAllMorphDrivers(rig, scn, prefix):
    from .driver import removeRigDrivers, removeTypedDrivers
    setupMorphPaths(scn, False)
    removeRigDrivers(rig)
    removeSelfRefs(rig)
    removeProps(rig, prefix)
    for ob in rig.children:
        if ob.type == 'MESH' and ob.data.shape_keys:
            removeTypedDrivers(ob.data.shape_keys, 'SINGLE_PROP')
            removeProps(ob, prefix)


def removeSelfRefs(rig):
    for pb in rig.pose.bones:
        if len(pb.constraints) > 0:
            cns = pb.constraints[0]
            if (cns.mute and
                cns.name == "Do Not Touch"):
                pb.constraints.remove(cns)


def removeProps(ob, prefix):
    ob.DazCustomMorphs = ob.DazCustomPoses = False
    for catgroup in ["DazMorphCats", "DazPoseCats"]:
        for cat in getattr(ob, catgroup):
            key = "DazShow"+cat.name
            if hasattr(ob, key):
                setattr(ob, key, False)
            for morph in cat.morphs:
                key = morph.prop
                if key in ob.keys():
                    ob[key] = 0.0
                    del ob[key]

    n = len(prefix)
    for key in ob.keys():
        if key[0:n] == prefix:
            ob[key] = 0.0
            del ob[key]
    for type in theMorphNames.keys():
        key = "Daz"+type
        if key in ob.keys():
            ob[key] = False
            del ob[key]


class DAZ_OT_RemoveMorphDrivers(bpy.types.Operator):
    bl_idname = "daz.remove_morph_drivers"
    bl_label = "Remove Morph Drivers"
    bl_description = "Remove drivers associated with morphs (not corrective shapekeys)"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return context.object

    def execute(self, context):
        try:
            rig = getRigFromObject(context.object)
            if rig:
                removeAllMorphDrivers(rig, context.scene, "Dz")
                updateScene(context)
                updateRig(rig, context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}

#-------------------------------------------------------------
#   Add and remove driver
#-------------------------------------------------------------

def getActiveShapeKey(ob):
    if ob.active_shape_key_index == 0:
        raise DazError("Cannot add/remove driver to first shapekey")
    skey = ob.active_shape_key
    if skey is None:
        raise DazError("Object %s has no active shapekey" % ob.name)
    return skey


class DAZ_OT_AddDriver(bpy.types.Operator):
    bl_idname = "daz.add_shapekey_driver"
    bl_label = "Add Driver"
    bl_description = "Add rig driver to active shapekey"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

    def execute(self, context):
        try:
            self.addDriver(context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}

    def addDriver(self, context):
        from .driver import makeShapekeyDriver
        ob = context.object
        skey = getActiveShapeKey(ob)
        rig = ob.parent
        if (rig and rig.type == 'ARMATURE'):
            sname = skey.name
            makeShapekeyDriver(ob, sname, skey.value, rig, sname)
            addToCategories(rig, [sname], "Shapekeys")
            ob.DazCustomMorphs = True
            rig.DazCustomMorphs = True


class DAZ_OT_RemoveDriver(bpy.types.Operator):
    bl_idname = "daz.remove_shapekey_driver"
    bl_label = "Remove Driver"
    bl_description = "Remove rig driver from active shapekey"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

    def execute(self, context):
        try:
            self.removeDriver(context.object)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}

    def removeDriver(self, ob):
        skey = getActiveShapeKey(ob)
        removeShapekeyDriver(ob, skey)
        rig = ob.parent
        if (rig and rig.type == 'ARMATURE' and
            skey.name in rig.keys()):
            del rig[skey.name]


def removeShapekeyDriver(ob, skey):
    adata = ob.data.shape_keys.animation_data
    if (adata and adata.drivers):
        for fcu in adata.drivers:
            words = fcu.data_path.split('"')
            if (words[0] == "key_blocks[" and
                words[1] == skey.name):
                ob.data.shape_keys.driver_remove(fcu.data_path)
                return
    raise DazError("Did not find driver for shapekey %s" % skey.name)

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def getRigFromObject(ob):
    if ob.type == 'ARMATURE':
        return ob
    else:
        ob = ob.parent
        if ob is None or ob.type != 'ARMATURE':
            return None
        return ob


class DAZ_OT_ToggleAllCats(bpy.types.Operator, UseOpenBool):
    bl_idname = "daz.toggle_all_cats"
    bl_label = "Toggle All Categories"
    bl_description = "Toggle all morph categories on and off"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object)

    def execute(self, context):
        try:
            ob = getRigFromObject(context.object)
            if ob:
                for key in ob.keys():
                    if key[0:7] == "DazShow":
                        ob[key] = self.useOpen
        except DazError:
            handleDazError(context)
        return {'FINISHED'}

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def isActive(rig, key, force=False):
    if force:
        return True
    elif "DzA"+key in rig.keys():
        return rig["DzA"+key]
    else:
        return True


def keyProp(rig, key, frame):
    rig.keyframe_insert('["%s"]' % key, frame=frame)


def unkeyProp(rig, key, frame):
    rig.keyframe_delete('["%s"]' % key, frame=frame)


def getPropFCurves(rig, key):
    if rig.animation_data and rig.animation_data.action:
        path = '["%s"]' % key
        return [fcu for fcu in rig.animation_data.action.fcurves if path == fcu.data_path]
    return []


def autoKeyProp(rig, key, scn, frame, force):
    if scn.tool_settings.use_keyframe_insert_auto:
        if force or getPropFCurves(rig, key):
            keyProp(rig, key, frame)


def pinProp(rig, scn, key, type, prefix, catgroup, frame):
    if rig:
        clearMorphs(rig, type, prefix, catgroup, scn, frame, True)
        rig[key] = 1.0
        autoKeyProp(rig, key, scn, frame, True)


class DAZ_OT_PinProp(bpy.types.Operator, KeyString, TypePrefixCat):
    bl_idname = "daz.pin_prop"
    bl_label = ""
    bl_description = "Pin property"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type in ['MESH', 'ARMATURE'])

    def execute(self, context):
        try:
            rig = getRigFromObject(context.object)
            scn = context.scene
            setupMorphPaths(scn, False)
            pinProp(rig, scn, self.key, self.type, self.prefix, self.catgroup, scn.frame_current)
            updateScene(context)
            updateRig(rig, context)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}

# ---------------------------------------------------------------------
#   Load Moho
# ---------------------------------------------------------------------

Moho = {
    "rest" : "Rest",
    "etc" : "K",
    "AI" : "AA",
    "O" : "OU",
    "U" : "OW",
    "WQ" : "AH",
    "L" : "L",
    "E" : "EH",
    "MBP" : "M",
    "FV" : "F"
}

def getVisemesPrefix(rig):
    return Visemes[rig.DazVisemes][2]


def loadMoho(context, filepath, offs):
    from .fileutils import safeOpen
    scn = context.scene
    ob = context.object
    if ob.type == 'ARMATURE':
        rig = ob
    elif ob.type == 'MESH':
        rig = ob.parent
    else:
        rig = None
    if rig is None:
        return
    setActiveObject(context, rig)
    bpy.ops.object.mode_set(mode='POSE')
    if rig.DazNewStyleExpressions:
        vprefix = "DzV"
        prefix = "DzV"
    else:
        vprefix = getVisemesPrefix(rig)
        prefix = ""
    auto = scn.tool_settings.use_keyframe_insert_auto
    scn.tool_settings.use_keyframe_insert_auto = True
    fp = safeOpen(filepath, "rU")
    for line in fp:
        words= line.split()
        if len(words) < 2:
            pass
        else:
            frame = int(words[0]) + offs
            if words[1] == "rest":
                clearMorphs(rig, "Visemes", prefix, None, scn, frame, True)
            else:
                key = vprefix + Moho[words[1]]
                print("MOI", frame, words[1], key)
                pinProp(rig, scn, key, "Visemes", prefix, None, frame)
    fp.close()
    #setInterpolation(rig)
    updateScene(context)
    updateRig(rig, context)
    scn.tool_settings.use_keyframe_insert_auto = auto
    print("Moho file %s loaded" % filepath)


class DAZ_OT_LoadMoho(bpy.types.Operator, DatFile, SingleFile):
    bl_idname = "daz.load_moho"
    bl_label = "Load Moho"
    bl_description = "Load Moho (.dat) file"
    bl_options = {'UNDO'}

    def execute(self, context):
        loadMoho(context, self.filepath, 1.0)
        return{'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

# ---------------------------------------------------------------------
#   Delete lipsync
# ---------------------------------------------------------------------

def getArmature(ob):
    if ob.type == 'MESH':
        ob = ob.parent
    if ob and ob.type == 'ARMATURE':
        return ob
    return None


def deleteLipsync(rig):
    if rig.animation_data is None:
        return
    act = rig.animation_data.action
    if act is None:
        return
    if rig.MhxFaceShapeDrivers:
        for fcu in act.fcurves:
            if (fcu.data_path[0:5] == '["Mhf' and
                fcu.data_path[5:9] in ["mout", "lips", "tong"]):
                    act.fcurves.remove(fcu)
        for key in getMouthShapes():
            rig["Mhf"+key] = 0.0
    elif rig.MhxFacePanel:
        for key in getMouthShapes():
            pb,_fac,idx = getBoneFactor(rig, key)
            path = 'pose.bones["%s"].location' % pb.name
            for fcu in act.fcurves:
                if fcu.data_path == path:
                    act.fcurves.remove(fcu)
                    pb.location[idx] = 0.0


class DAZ_OT_DeleteLipsync(bpy.types.Operator):
    bl_idname = "daz.delete_lipsync"
    bl_label = "Delete Lipsync"
    bl_description = "Delete F-curves associated with lipsync"
    bl_options = {'UNDO'}

    def execute(self, context):
        rig = getArmature(context.object)
        if rig:
            deleteLipsync(rig)
        updateScene(context)
        updateRig(rig, context)
        return{'FINISHED'}

#-------------------------------------------------------------
#   Convert pose to shapekey
#-------------------------------------------------------------

class DAZ_OT_ConvertMorphsToShapes(bpy.types.Operator, MorphTypes):
    bl_idname = "daz.convert_morphs_to_shapes"
    bl_label = "Convert Morphs To Shapes"
    bl_description = "Convert face rig poses to shapekeys"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

    def draw(self, context):
        self.layout.prop(self, "units")
        self.layout.prop(self, "expressions")
        self.layout.prop(self, "visemes")
        self.layout.prop(self, "other")

    def execute(self, context):
        try:
            ob = context.object
            rig = ob.parent
            if rig and rig.type == 'ARMATURE':
                self.convertToShapes(context, rig, ob)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.invoke_props_dialog(self)
        return {'RUNNING_MODAL'}
    
    
    def convertToShapes(self, context, rig, ob):    
        from .daz import getPropGroupProps
        keys = getPropGroupProps(rig)
        keys.sort()
        for key in keys:
            rig[key] = 0.0
        for key in keys:
            mname = self.getMorphName(key, ob)
            if (ob.data.shape_keys and 
                mname in ob.data.shape_keys.key_blocks.keys()):
                continue
            if mname:
                for mod in ob.modifiers:
                    if mod.type == 'ARMATURE':
                        rig[key] = 1.0
                        updateScene(context)
                        updateRig(rig, context)
                        self.applyArmature(ob, rig, mod, mname)
                        rig[key] = 0.0
                        break
        updateScene(context)
        updateRig(rig, context)
        updateDrivers(rig)


    def getMorphName(self, key, ob):
        if key[0:3] == "DzU" and self.units:
            return key[3:]
        if key[0:3] == "DzE" and self.expressions:
            return key[3:]
        if key[0:3] == "DzV" and self.visemes:
            return key[3:]
        if self.other and key[0:2] != "Dz" and key[0:3] != "Daz":
            return key
        return None                
    

    def applyArmature(self, ob, rig, mod, mname):
        mod.name = mname
        bpy.ops.object.modifier_apply(apply_as='SHAPE', modifier=mname)
        skey = ob.data.shape_keys.key_blocks[mname]
        skey.value = 0.0
        offsets = [(skey.data[vn].co - v.co).length for vn,v in enumerate(ob.data.vertices)]
        omax = max(offsets)
        omin = min(offsets)
        eps = 1e-2 * ob.DazScale    # eps = 0.1 mm
        if abs(omax) < eps and abs(omin) < eps:
            idx = ob.data.shape_keys.key_blocks.keys().index(skey.name)
            ob.active_shape_key_index = idx
            bpy.ops.object.shape_key_remove()
            ob.active_shape_key_index = 0
        nmod = ob.modifiers.new(rig.name, "ARMATURE")
        nmod.object = rig
        nmod.use_deform_preserve_volume = True   
        for i in range(len(ob.modifiers)-1):
            bpy.ops.object.modifier_move_up(modifier=nmod.name)

#-------------------------------------------------------------
#   Property groups, for drivers
#-------------------------------------------------------------

classes = [
    DAZ_OT_Update,
    DAZ_OT_SelectAll,
    DAZ_OT_SaveFavorites,
    DAZ_OT_LoadFavorites,
    DAZ_OT_LoadAllUnits,
    DAZ_OT_LoadAllExpressions,
    DAZ_OT_LoadAllVisemes,
    DAZ_OT_LoadAllCorrectives,
    DAZ_OT_ImportMorph,
    DAZ_OT_RenameCategoryOK,
    DAZ_OT_RemoveCategoryOK,
    DAZ_OT_ChangeCategoryCancel,
    DAZ_OT_ChangeCategory,
    DAZ_OT_Prettify,
    DAZ_OT_ForceUpdate,
    DAZ_OT_ActivateAll,
    DAZ_OT_DeactivateAll,
    DAZ_OT_ClearMorphs,
    DAZ_OT_UpdateMorphs,
    DAZ_OT_AddKeysets,
    DAZ_OT_KeyMorphs,
    DAZ_OT_UnkeyMorphs,
    DAZ_OT_UpdatePropLimits,
    DAZ_OT_RemoveMorphDrivers,
    DAZ_OT_AddDriver,
    DAZ_OT_RemoveDriver,
    DAZ_OT_ToggleAllCats,
    DAZ_OT_PinProp,
    DAZ_OT_LoadMoho,
    DAZ_OT_DeleteLipsync,
    DAZ_OT_ConvertMorphsToShapes,

    #DazCategory,
    #DazCustomGroup,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Object.DazCustomMorphs = BoolProperty(default = False)
    bpy.types.Object.DazCustomPoses = BoolProperty(default = False)

    bpy.utils.register_class(DazCustomGroup)
    bpy.utils.register_class(DazCategory)

    bpy.types.Object.DazMorphCats = CollectionProperty(type = DazCategory)
    bpy.types.Object.DazPoseCats = CollectionProperty(type = DazCategory)

    bpy.types.Scene.DazMorphCatsOpen = BoolProperty(default = False)
    bpy.types.Scene.DazPoseCatsOpen = BoolProperty(default = False)

    bpy.types.Scene.DazMorphCatsContent = EnumProperty(
        items = [],
        name = "Morph")
    bpy.types.Scene.DazPoseCatsContent = EnumProperty(
        items = [],
        name = "Pose")

    bpy.types.Scene.DazNewCatName = StringProperty(
        name = "New Name",
        default = "Name")



def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    bpy.utils.unregister_class(DazCustomGroup)
    bpy.utils.unregister_class(DazCategory)
