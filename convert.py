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
from .error import handleDazError, DazError
from .utils import *
import os
from mathutils import *
if bpy.app.version < (2,80,0):
    from .buttons27 import JsonExportFile, JsonFile, SingleFile, SkelPoseBool
else:
    from .buttons28 import JsonExportFile, JsonFile, SingleFile, SkelPoseBool

Converters = {}
TwistBones = {}
RestPoses = {}
IkPoses = {}

#-------------------------------------------------------------
#   Save current pose
#-------------------------------------------------------------

def saveStringToFile(filepath, string):
    from .fileutils import safeOpen
    fp = safeOpen(filepath, "w")
    fp.write(string)
    fp.close()
    print("Saved to %s" % filepath)


class DAZ_OT_SaveCurrentPose(bpy.types.Operator, JsonExportFile, SkelPoseBool):
    bl_idname = "daz.save_current_pose"
    bl_label = "Save Current Pose"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'ARMATURE')

    def execute(self, context):
        self.save(context.object, self.filepath)
        return{'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def save(self, rig, filepath):
        rolls = {}
        bpy.ops.object.mode_set(mode='EDIT')
        for eb in rig.data.edit_bones:
            rolls[eb.name] = eb.roll
        bpy.ops.object.mode_set(mode='POSE')

        string = ('{\n' +
            '\t"character":\t"%s",\n' % rig.name +
            '\t"scale":\t"1.0",')

        if self.skeleton:
            string += '\n\n\t"skeleton":\t{'
            for pb in rig.pose.bones:
                string += (
                    '\n\t\t"%s": [' % pb.name +
                    '\n\t\t\t"%s",' % pb.rotation_mode +
                    '\n\t\t\t%.4f' % rolls[pb.name] +
                    '\n\t\t],')
            string = string[:-1] + '\n\t},'

        if self.pose:
            string += '\n\n\t"pose":\t{'
            for pb in rig.pose.bones:
                if pb.bone.select:
                    euler = pb.matrix.to_3x3().to_euler()
                    string += (
                        '\n\t\t"%s": [' % pb.name +
                        '\n\t\t\t[%.4f, %.4f, %.4f],' % tuple(euler) +
                        '\n\t\t\t[%.4f, %.4f, %.4f],' % tuple(pb.bone.DazOrientation) +
                        '\n\t\t\t"%s",' % pb.DazRotMode +
                        '\n\t\t\t%.4f' % rolls[pb.name] +
                        '\n\t\t],')
            string = string[:-1] + '\n\t},'

        string = string[:-1] + '\n}\n'
        saveStringToFile(filepath, string)

#-------------------------------------------------------------
#   Load pose
#-------------------------------------------------------------

def getCharacter(rig):
    if rig.DazMesh:
        char = rig.DazMesh.lower().replace("-","_").replace("genesis", "genesis_")
        if char[-1] == "_":
            char = char[:-1]
        print("Character: %s" % char)
        return char
    else:
        return None


def loadRestPoseEntry(character, table, folder):
    import json
    from .fileutils import safeOpen
    if character in table.keys():
        return
    filepath = os.path.join(folder, character +  ".json")
    print("Load", filepath)
    if not os.path.exists(filepath):
        raise DazError("File %s    \n does not exist" % filepath)
    else:
        with safeOpen(filepath, "rU") as fp:
            data = json.load(fp)
    table[character] = data


def getOrientation(character, bname, rig):
    from .globvars import theRestPoseFolder
    if rig and bname in rig.pose.bones.keys():
        pb = rig.pose.bones[bname]
        return pb.bone.DazOrientation, pb.DazRotMode

    loadRestPoseEntry(character, RestPoses, theRestPoseFolder)
    bones = RestPoses[character]["pose"]
    if bname in bones.keys():
        vec, orient, xyz = bones[bname]
        return orient, xyz
    else:
        return None, "XYZ"


def loadPose(rig, character, table, modify):
    root = None
    for pb in rig.pose.bones:
        if pb.parent is None:
            root = pb
            break
    if "skeleton" in table[character]:
        modifySkeleton(rig, table[character]["skeleton"])
    loadBonePose(root, table[character]["pose"])


def modifySkeleton(rig, skel):
    bpy.ops.object.mode_set(mode='EDIT')
    for eb in rig.data.edit_bones:
        bname = getBoneName(eb.name, skel)
        if bname in skel.keys():
            eb.roll = skel[bname][1]
    bpy.ops.object.mode_set(mode='POSE')
    for pb in rig.pose.bones:
        bname = getBoneName(pb.name, skel)
        if bname in skel.keys():
            pb.rotation_mode = skel[bname][0]


def getBoneName(bname, bones):
    if bname in bones.keys():
        return bname
    elif (bname[-3:] == "Drv" and
          bname[:-3] in bones.keys()):
        return bname[:-3]
    elif (bname[-4:] == "Copy" and
          bname[:-4] in bones.keys()):
        return bname[:-4]
    else:
        return None


def loadBonePose(pb, pose):
    pbname = getBoneName(pb.name, pose)
    if pbname and pb.name[:-4] != "Copy":
        vec, pb.bone.DazOrientation, pb.DazRotMode = pose[pbname]
        euler = Euler(vec)
        mat = euler.to_matrix()
        rmat = pb.bone.matrix_local.to_3x3()
        if pb.parent:
            par = pb.parent
            rmat = Mult2(par.bone.matrix_local.to_3x3().inverted(), rmat)
            mat = Mult2(par.matrix.to_3x3().inverted(), mat)
        bmat = Mult2(rmat.inverted(), mat)
        pb.matrix_basis = bmat.to_4x4()
        for n in range(3):
            if pb.lock_rotation[n]:
                pb.rotation_euler[n] = 0
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.object.mode_set(mode='POSE')

    if pb.name != "head":
        for child in pb.children:
            loadBonePose(child, pose)


class DAZ_OT_LoadPose(bpy.types.Operator, JsonFile, SingleFile):
    bl_idname = "daz.load_pose"
    bl_label = "Load Pose"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'ARMATURE')

    def execute(self, context):
        folder = os.path.dirname(self.filepath)
        character = os.path.splitext(os.path.basename(self.filepath))[0]
        table = {}
        loadRestPoseEntry(character, table, folder)
        loadPose(context.object, character, table, False)
        print("Pose %s loaded" % self.filepath)
        return{'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

#-------------------------------------------------------------
#   Optimize pose for Rigify
#-------------------------------------------------------------

def optimizePose(context):
    from .globvars import theIkPoseFolder
    rig = context.object
    char = getCharacter(rig)
    if char is None:
        raise DazError("Did not recognize character")
    loadRestPoseEntry(char, IkPoses, theIkPoseFolder)
    loadPose(rig, char, IkPoses, False)


class DAZ_OT_OptimizePoses(bpy.types.Operator):
    bl_idname = "daz.optimize_pose"
    bl_label = "Optimize Pose For IK"
    bl_description = "Optimize rest pose for IK. Incompatible with pose loading."
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'ARMATURE')

    def execute(self, context):
        try:
            optimizePose(context)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}

#-------------------------------------------------------------
#   Convert Rig
#-------------------------------------------------------------

SourceRig = {
    "genesis" : "genesis1",
    "genesis_2_female" : "genesis2",
    "genesis_2_male" : "genesis2",
    "genesis_3_female" : "genesis3",
    "genesis_3_male" : "genesis3",
    "genesis_8_female" : "genesis8",
    "genesis_8_male" : "genesis8",
}

def convertRig(context):
    from .merge import applyRestPoses
    from .globvars import theRestPoseFolder
    global RestPoses

    rig = context.object
    scn = context.scene
    loadRestPoseEntry(scn.DazNewRig, RestPoses, theRestPoseFolder)
    scale = 1.0
    if scn.DazNewRig in SourceRig.keys():
        modify = False
        src = SourceRig[scn.DazNewRig]
        conv,twists = getConverter(src, rig)
        if conv:
            renameBones(rig, conv)
    else:
        modify = True
        src = scn.DazNewRig
        table = RestPoses[src]
        if "translate" in table.keys():
            renameBones(rig, table["translate"])
        if "scale" in table.keys():
            scale = table["scale"] * rig.DazScale
    loadPose(rig, scn.DazNewRig, RestPoses, modify)
    #applyRestPoses(context)
    rig.DazRig = src
    print("Rig converted to %s" % scn.DazNewRig)
    if scale != 1.0:
        raise DazError("Use scale = %.5f when loading BVH files.       " % scale, True)


def renameBones(rig, conv):
    print(conv.items())
    bpy.ops.object.mode_set(mode='EDIT')
    for eb in rig.data.edit_bones:
        if eb.name in conv.keys():
            data = conv[eb.name]
            if isinstance(data, list):
                eb.name = data[0]
                if data[1] == "reverse":
                    head = tuple(eb.head)
                    tail = tuple(eb.tail)
                    eb.head = (1,2,3)
                    eb.tail = head
                    eb.head = tail
                    #bpy.ops.object.mode_set(mode='OBJECT')
                    #bpy.ops.object.mode_set(mode='EDIT')
            else:
                eb.name = data
    bpy.ops.object.mode_set(mode='OBJECT')


class DAZ_OT_ConvertRigPose(bpy.types.Operator):
    bl_idname = "daz.convert_rig"
    bl_label = "Convert DAZ Rig"
    bl_description = "Convert current DAZ rig to other DAZ rig"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and ob.DazRig[0:7] == "genesis")

    def execute(self, context):
        try:
            convertRig(context)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}

#-------------------------------------------------------------
#   Bone conversion
#-------------------------------------------------------------

TwistBones["genesis3"] = [
    ("lShldrBend", "lShldrTwist"),
    ("rShldrBend", "rShldrTwist"),
    ("lForearmBend", "lForearmTwist"),
    ("rForearmBend", "rForearmTwist"),
    ("lThighBend", "lThighTwist"),
    ("rThighBend", "rThighTwist"),
]
TwistBones["genesis8"] = TwistBones["genesis3"]


def getConverter(stype, trg):
    if stype == "genesis8":
        stype = "genesis3"
    trgtype = trg.DazRig
    if trgtype == "genesis8":
        trgtype = "genesis3"

    if stype == "" or trgtype == "":
        return {},[]
    if (stype in TwistBones.keys() and
        trgtype not in TwistBones.keys()):
        twists = TwistBones[stype]
    else:
        twists = []

    if stype == trgtype:
        return {},twists
    if trgtype == "mhx":
        cname = stype[:-1] + "-mhx"
    elif trgtype[0:6] == "rigify":
        cname = stype[:-1] + "-" + trgtype
    else:
        cname = stype + "-" + trgtype

    conv = getConverterEntry(cname)
    if not conv:
        print("No converter", stype, trg.DazRig)
    return conv, twists


def getConverterEntry(cname):
    import json
    from .fileutils import safeOpen
    if cname in Converters.keys():
        return Converters[cname]
    else:
        folder = os.path.join(os.path.dirname(__file__), "data", "converters")
        filepath = os.path.join(folder, cname + ".json")
        if os.path.exists(filepath):
            with safeOpen(filepath, "rU") as fp:
                conv = Converters[cname] = json.load(fp)
            return conv
    return {}

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_SaveCurrentPose,
    DAZ_OT_LoadPose,
    DAZ_OT_OptimizePoses,
    DAZ_OT_ConvertRigPose,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
