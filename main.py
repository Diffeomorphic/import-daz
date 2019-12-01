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
from .settings import theSettings
from .error import *
from .utils import *
if bpy.app.version < (2,80,0):
    from .buttons27 import DazFile, SingleFile
else:
    from .buttons28 import DazFile, SingleFile

#------------------------------------------------------------------
#   Import file
#------------------------------------------------------------------

def getMainAsset(filepath, context, btn):
    import time
    from .objfile import getFitFile, fitToFile

    scn = context.scene
    theSettings.forImport(btn, scn)
    print("Scale", theSettings.scale)
    t1 = time.clock()

    from .fileutils import getFilePath
    path = getFilePath(filepath, ["duf", "dsf", "dse"])
    if path is None:
        raise DazError("Found no .duf file matching\n%s        " % filepath)
    filepath = path
    print("\nLoading %s" % filepath)
    if theSettings.fitFile:
        getFitFile(filepath)

    from .readfile import readDufFile
    struct = readDufFile(filepath)

    print("Parsing data")
    from .files import parseAssetFile
    main = parseAssetFile(struct, toplevel=True)
    if main is None:
        msg = ("File not found:  \n%s      " % filepath)
        raise DazError(msg)

    if theSettings.fitFile:
        fitToFile(filepath, main.nodes)

    print("Preprocessing...")
    for asset,inst in main.nodes:
        inst.preprocess(context)

    print("Building objects...")
    grpname = os.path.splitext(os.path.basename(filepath))[0].capitalize()
    if theSettings.group and bpy.app.version >= (2,80,0):
        makeNewSceneCollection(grpname, context)

    for asset in main.materials:
        asset.build(context)
    for asset,inst in main.nodes:
        asset.build(context, inst)      # Builds armature
    for asset,inst in main.modifiers:
        asset.build(context, inst)      # Builds morphs
    for asset,inst in main.nodes:
        asset.postbuild(context, inst)
    # Need to update scene before calculating object areas
    updateScene(context)
    for asset in main.materials:
        asset.postbuild(context)

    print("Postprocessing...")
    for asset,inst in main.nodes:
        asset.postprocess(context, inst)
    for asset,inst in main.modifiers:
        asset.postprocess(context, inst)
    for _,inst in main.nodes:
        inst.pose(context)
    for asset,inst in main.modifiers:
        asset.postbuild(context, inst)

    if main.renderOptions:
        main.renderOptions.build(context)

    if (theSettings.useMaterials and
        theSettings.chooseColors != 'WHITE'):
        for asset,inst in main.nodes:
            asset.guessColor(scn, theSettings.chooseColors, inst)

    rig,grp = renameAndGroup(main, grpname, context)
    from .node import resetInstancedObjects
    resetInstancedObjects(context, grp)
    finishMain(filepath, t1)
    if theSettings.missingAssets:
        msg = ("Some assets were not found.\nCheck that all Daz paths have been set up correctly.        ")
        raise DazError(msg, warning=True)


def renameAndGroup(main, grpname, context):
    from .figure import FigureInstance
    from .finger import getFingeredCharacter

    for _,inst in main.nodes:
        if isinstance(inst, FigureInstance):
            rig = inst.rna
            inst.rna.name = inst.name

    rig = None
    mesh = None
    for asset,inst in main.nodes:
        if isinstance(inst, FigureInstance):
            rig,mesh,char = getFingeredCharacter(inst.rna)
            if rig and mesh:
                rig.DazMesh = mesh.DazMesh = char
                activateObject(context, rig)
            elif mesh:
                mesh.DazMesh = char

    if theSettings.rename and rig:
        print("Renaming", grpname)
        rig.name = rig.data.name = grpname
        if mesh:
            mesh.name = mesh.data.name = "Mesh"
        for ob in rig.children:
            ob.name = ob.data.name = grpname + "_" + ob.name

    if theSettings.group and bpy.app.version < (2,80,0):
        grp = groupInstances(grpname, main, context)
    else:
        grp = None
    return rig, grp


def makeNewSceneCollection(grpname, context):
    colls = context.scene.collection
    coll = bpy.data.collections.new(name=grpname)
    colls.children.link(coll)
    theSettings.collection = coll


def groupInstances(grpname, main, context):
    from .node import Instance
    from .figure import FigureInstance
    from .bone import BoneInstance
    from .geometry import GeoNode

    print("Grouping", grpname)
    grp = bpy.data.groups.new(grpname)
    for asset,inst in main.nodes:
        if isinstance(inst, FigureInstance):
            addToGroup(inst, grp)
            for geonode in inst.geometries:
                addToGroup(geonode, grp)
        elif isinstance(inst, GeoNode):
            addToGroup(inst, grp)
        elif isinstance(inst, BoneInstance):
            pass
        elif isinstance(inst, Instance):
            addToGroup(inst, grp)
            for geonode in inst.geometries:
                addToGroup(geonode, grp)
    return grp


def addToGroup(inst, grp):
    ob = inst.rna
    if (isinstance(ob, bpy.types.Object) and
        ob.name not in grp.objects.keys()):
        grp.objects.link(ob)


def finishMain(filepath, t1):
    import time
    from .asset import clearAssets

    t2 = time.clock()
    print("File %s loaded in %.3f seconds" % (filepath, t2-t1))
    clearAssets()

#------------------------------------------------------------------
#   Reparent extra bones
#------------------------------------------------------------------

def reparentBones(rig):
    par = rig.data.edit_bones.active
    for eb in rig.data.edit_bones:
        if eb.select and eb != par:
            eb.parent = par


class DAZ_OT_ReparentBones(bpy.types.Operator):
    bl_idname = "daz.reparent_bones"
    bl_label = "Reparent Bones"
    bl_description = "Reparent selected bones to active"
    bl_options = {'UNDO'}

    def execute(self, context):
        try:
            reparentBones(context.object)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}

#------------------------------------------------------------------
#   Decode file
#------------------------------------------------------------------

class DAZ_OT_DecodeFile(bpy.types.Operator, DazFile, SingleFile):
    bl_idname = "daz.decode_file"
    bl_label = "Decode File"
    bl_description = "Decode a gzipped DAZ file (*.duf, *.dsf) to a text file"
    bl_options = {'UNDO'}

    def execute(self, context):
        import gzip
        try:
            self.decodeFile()
        except DazError:
            handleDazError(context)
        return{'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def decodeFile(self):
        import gzip
        from .asset import getDazPath
        from .fileutils import safeOpen
    
        print("Decode",  self.filepath)
        try:
            with gzip.open(self.filepath, 'rb') as fp:
                bytes = fp.read()
        except IOError:
            raise DazError("Cannot decode:\n%s" % self.filepath)
        string = bytes.decode("utf-8")
        newfile = os.path.splitext(self.filepath)[0] + ".txt"
        with safeOpen(newfile, "w") as fp:
            fp.write(string)
        print("%s written" % newfile)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ReparentBones,
    DAZ_OT_DecodeFile,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
