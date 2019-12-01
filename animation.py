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
from bpy.props import *
import math
import os
from mathutils import *
from .error import *
from .utils import *
from .transform import Transform
from .settings import theSettings
from .globvars import theDazExtensions, thePoserExtensions, theRestPoseItems
if bpy.app.version < (2,80,0):
    from .buttons27 import AnimatorFile, MultiFile, ConvertOptions, AffectOptions, ActionOptions, PoseLibOptions
else:
    from .buttons28 import AnimatorFile, MultiFile, ConvertOptions, AffectOptions, ActionOptions, PoseLibOptions


def framesToVectors(frames):
    vectors = {}
    for idx in frames.keys():
        for t,y in frames[idx]:
            if t not in vectors.keys():
                vectors[t] = Vector((0,0,0))
            vectors[t][idx] = y
    return vectors


def vectorsToFrames(vectors):
    frames = {}
    for idx in range(3):
        frames[idx] = [[t,vectors[t][idx]] for t in vectors.keys()]
    return frames


def combineBendTwistAnimations(anim, twists):
    for (bend,twist) in twists:
        if twist in anim.keys():
            if bend in anim.keys():
                addTwistFrames(anim[bend], anim[twist])
            else:
                anim[bend] = {"rotation" : halfRotation(anim[twist]["rotation"])}


def addTwistFrames(bframes, tframes):
    if "rotation" not in bframes:
        if "rotation" not in tframes:
            return bframes
        else:
            bframes["rotation"] = halfRotation(tframes["rotation"])
            return bframes
    elif "rotation" not in tframes:
        return bframes
    for idx in bframes["rotation"].keys():
        bkpts = dict(bframes["rotation"][idx])
        if idx in tframes["rotation"].keys():
            tkpts = tframes["rotation"][idx]
            for n,y in tkpts:
                if n in bkpts.keys():
                    bkpts[n] += y/2
                else:
                    bkpts[n] = y/2
        kpts = list(bkpts.items())
        kpts.sort()
        bframes["rotation"][idx] = kpts


def halfRotation(frames):
    nframes = {}
    for idx in frames.keys():
        nframes[idx] = [(n,y/2) for n,y in frames[idx]]
    return nframes

#-------------------------------------------------------------
#   Animations
#-------------------------------------------------------------

def extendFcurves(rig, frame0, frame1):
    act = rig.animation_data.action
    if act is None:
        return
    for fcu in act.fcurves:
        if fcu.keyframe_points:
            value = fcu.evaluate(frame0)
            print(fcu.data_path, fcu.array_index, value)
            for frame in range(frame0, frame1):
                fcu.keyframe_points.insert(frame, value, options={'FAST'})


def addFrames(bname, channel, nmax, cname, frames):
    for comp in range(nmax):
        if comp not in channel.keys():
            continue
        for t,y in channel[comp]:
            n = t*theSettings.fps
            if theSettings.integerFrames:
                n = int(round(n))
            if n not in frames.keys():
                frame = frames[n] = {}
            else:
                frame = frames[n]
            if bname not in frame.keys():
                bframe = frame[bname] = {}
            else:
                bframe = frame[bname]
            if cname == "value":
                bframe[cname] = {0: y}
            else:
                if cname not in bframe.keys():
                    bframe[cname] = Vector((0,0,0))
                bframe[cname][comp] = y

KnownRigs = [
    "Genesis",
    "GenesisFemale",
    "GenesisMale",
    "Genesis2",
    "Genesis2Female",
    "Genesis2Male",
    "Genesis3",
    "Genesis3Female",
    "Genesis3Male",
]


def addTransform(node, channel, bones, key):
    if channel in node.keys():
        if key not in bones.keys():
            bone = bones[key] = {}
        else:
            bone = bones[key]
        if channel not in bone.keys():
            bone[channel] = {}
        for struct in node[channel]:
            comp = struct["id"]
            value = struct["current_value"]
            bone[channel][getIndex(comp)] = [[0, value]]


def getChannel(url):
    words = url.split(":")
    if len(words) == 2:
        key = words[0]
    elif len(words) == 3:
        words = words[1].rsplit("/",1)
        if len(words) == 2:
            key = words[1].rsplit("#")[-1]
        else:
            return None,None,None
    else:
        return None,None,None

    words = url.rsplit("?", 2)
    if len(words) != 2:
        return None,None,None
    words = words[1].split("/")
    if len(words) in [2,3]:
        channel = words[0]
        comp = words[1]
        return key,channel,comp
    else:
        return None,None,None


#-------------------------------------------------------------
#   Frame converter class
#-------------------------------------------------------------

class FrameConverter:

    def getConv(self, bones, rig):
        from .figure import getRigType
        from .convert import getConverter
        from collections import OrderedDict
        stype = getRigType(bones)
        conv,twists = getConverter(stype, rig)
        if not conv:
            conv = {}
        bonemap = OrderedDict([(bname,bname) for bname in rig.pose.bones.keys()])
        return conv, twists, bonemap


    def getLocks(self, rig, conv):
        locks = []
        if rig.DazRig[0:6] == "rigify":
            for bname in conv.values():
                if (bname in rig.pose.bones.keys() and
                    bname not in ["torso"]):
                    pb = rig.pose.bones[bname]
                    locks.append((pb, tuple(pb.lock_location)))
                    pb.lock_location = (True, True, True)
        return locks


    def convertAnimations(self, anims, rig):
        if rig.type != 'ARMATURE':
            return anims, []
        conv,twists,bonemap = self.getConv(anims[0][0], rig)
        locks = self.getLocks(rig, conv)

        nanims = []
        for banim,vanim in anims:
            #combineBendTwistAnimations(banim, twists)
            nbanim = {}
            for bname,frames in banim.items():
                if bname in conv.keys():
                    nname = conv[bname]
                else:
                    nname = bname
                bonemap[bname] = nname
                nbanim[nname] = frames
            nanims.append((nbanim,vanim))

        if self.convertPoses:
            nanims = self.convertAllFrames(nanims, rig, bonemap)
        return nanims, locks


    def convertAllFrames(self, anims, rig, bonemap):
        from .convert import getCharacter

        trgCharacter = getCharacter(rig)
        if trgCharacter is None:
            return anims
        restmats = {}
        nrestmats = {}
        transmats = {}
        ntransmats = {}
        xyzs = {}
        nxyzs = {}
        parents = dict([(bone.name, bone.parent.name) for bone in rig.data.bones if bone.parent])
        for bname,nname in bonemap.items():
            self.getMatrices(bname, None, self.srcCharacter, parents, restmats, transmats, xyzs)
            self.getMatrices(nname, rig, trgCharacter, parents, nrestmats, ntransmats, nxyzs)

        for banim,vanim in anims:
            nbanim = {}
            for bname,nname in bonemap.items():
                if nname in banim.keys() and nname in ntransmats.keys() and bname in transmats.keys():
                    frames = banim[nname]
                    if "rotation" in frames.keys():
                        nframes = self.convertFrames(ntransmats[nname].inverted(), transmats[bname], xyzs[bname], nxyzs[nname], frames["rotation"])

        return anims


    def getMatrices(self, bname, rig, char, parents, restmats, transmats, xyzs):
        from .convert import getOrientation

        orient,xyzs[bname] = getOrientation(char, bname, rig)
        if orient is None:
            return
        restmats[bname] = Euler(Vector(orient)*D, 'XYZ').to_matrix()

        orient = None
        if bname in parents.keys():
            orient,xyz = getOrientation(char, parents[bname], rig)
            if orient:
                parmat = Euler(Vector(orient)*D, 'XYZ').to_matrix()
                transmats[bname] = Mult2(restmats[bname], parmat.inverted())
        if orient is None:
            transmats[bname] = Matrix().to_3x3()


    def convertFrames(self, amat, bmat, xyz, nxyz, frames):
        vecs = framesToVectors(frames)
        nvecs = {}
        for t,vec in vecs.items():
            mat = Euler(vec*D, xyz).to_matrix()
            nmat = Mult3(amat, mat, bmat)
            nvecs[t] = Vector(nmat.to_euler(nxyz))/D
        return vectorsToFrames(nvecs)

#-------------------------------------------------------------
#   AnimatorBase class
#-------------------------------------------------------------

class AnimatorBase(AnimatorFile, MultiFile, FrameConverter):
    lockMeshes = False

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type in ['MESH', 'ARMATURE'])


    def execute(self, context):
        try:
            self.getAnimations(context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}


    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


    def getSingleAnimation(self, filepath, rig, scn, offset, missing):
        from .readfile import readAssetFile
        from .driver import setFloatProp

        if filepath is None:
            return
        struct = readAssetFile(filepath)
        if "scene" not in struct.keys():
            return offset
        animations = self.parseAnimation(struct["scene"])
        if rig.type == 'ARMATURE':
            bpy.ops.object.mode_set(mode='POSE')
            self.prepareRig(rig)
        if self.useClearPose:
            self.clearPose(rig, offset)
        animations,locks = self.convertAnimations(animations, rig)
        if self.useDrivers:
            prop = os.path.splitext(os.path.basename(filepath))[0]
            setFloatProp(rig, prop, 0.0)
        else:
            prop = None
        result = self.animateBones(rig, scn, animations, offset, prop, filepath, missing)
        for pb,lock in locks:
            pb.lock_location = lock
        return result


    def prepareRig(self, rig):
        if rig.DazRig == "rigify":
            for n in [2,5,6,9,12,15,28]:
                rig.data.layers[n] = True
            for bname in ["hand.ik.L", "hand.ik.R",
                          "foot.ik.L", "foot.ik.R"]:
                if bname in rig.pose.bones.keys():
                    pb = rig.pose.bones[bname]
                    pb["ik_fk_switch"] = 0.0
            if "head.001" in rig.pose.bones.keys():
                pb = rig.pose.bones["head.001"]
                pb["neck_follow"] = 0.0
        elif rig.DazRig == "rigify2":
            for n in [3,5,8,11,14,17]:
                rig.data.layers[n] = True
            for bname in ["upper_arm_parent.L", "upper_arm_parent.R",
                          "thigh_parent.L", "thigh_parent.R"]:
                if bname in rig.pose.bones.keys():
                    pb = rig.pose.bones[bname]
                    pb["IK_FK"] = 1.0
            if "torso" in rig.pose.bones.keys():
                pb = rig.pose.bones["torso"]
                pb["neck_follow"] = 1.0
                pb["head_follow"] = 1.0
        elif rig.DazRig == "mhx":
            from .mhx import fkLayers
            layers = fkLayers()
            for n in range(32):
                rig.data.layers[n] = (n in layers)
            for pname in ["MhaArmIk_L", "MhaArmIk_R", "MhaLegIk_L", "MhaLegIk_R"]:
                rig[pname] = 0.0


    def parseAnimation(self, struct):
        animations = []
        bones = {}
        values = {}
        animations.append((bones, values))

        if self.loadType == 'NODES':
            if "nodes" in struct.keys():
                for node in struct["nodes"]:
                    key = node["id"]
                    addTransform(node, "translation", bones, key)
                    addTransform(node, "rotation", bones, key)
            elif self.verbose:
                print("No nodes in this file")

        elif self.loadType in ['POSES', 'ANIMATIONS']:
            if "animations" in struct.keys():
                for anim in struct["animations"]:
                    if "url" in anim.keys():
                        key,channel,comp = getChannel(anim["url"])
                        if channel is None:
                            continue
                        elif channel == "value":
                            if self.affectValues:
                                values[key] = getAnimKeys(anim)
                        elif channel in ["translation", "rotation", "scale"]:
                            if key not in bones.keys():
                                bone = bones[key] = {
                                    "translation": {},
                                    "rotation": {},
                                    "scale": {},
                                    }
                            bones[key][channel][getIndex(comp)] = getAnimKeys(anim)
                        else:
                            print("Unknown channel:", channel)

            elif "extra" in struct.keys():
                for extra in struct["extra"]:
                    if extra["type"] == "studio/scene_data/aniMate":
                        msg = ("Animation with aniblocks.\n" +
                               "In aniMate Lite tab, right-click         \n" +
                               "and Bake To Studio Keyframes.")
                        print(msg)
                        raise DazError(msg)

            elif self.verbose:
                print("No animations in this file")

        return animations


    def clearPose(self, rig, frame):
        tfm = Transform()
        tfm.setRna(rig)
        if self.insertKeys:
            tfm.insertKeys(rig, None, frame, rig.name, self.driven)
        if rig.type != 'ARMATURE':
            return
        for pb in rig.pose.bones:
            if pb.bone.select or not self.selectedOnly:
                pb.location = (0,0,0)
                pb.rotation_euler = (0,0,0)
                pb.rotation_quaternion = (1,0,0,0)
                if self.insertKeys:
                    tfm.insertKeys(rig, pb, frame, pb.name, self.driven)
        for key in rig.keys():
            if key[0:2] == "Dz" and key[0:3] != "DzA":
                rig[key] = 0.0
                if self.insertKeys:
                    rig.keyframe_insert('["%s"]' % key, frame=frame, group=key)


    def animateBones(self, rig, scn, animations, offset, prop, filepath, missing):
        from .driver import setFloatProp

        if self.affectValues:
            props = {}
            taken = {}
            for prop in rig.keys():
                key = prop[3:].lower()
                key = stripKey(key)
                props[key] = prop
                taken[key] = False

        errors = {}
        for banim,vanim in animations:
            frames = {}
            n = -1
            for bname, channels in banim.items():
                if "rotation" in channels.keys():
                    addFrames(bname, channels["rotation"], 3, "rotation", frames)
                if "translation" in channels.keys():
                    addFrames(bname, channels["translation"], 3, "translation", frames)
                if "scale" in channels.keys():
                    addFrames(bname, channels["scale"], 3, "scale", frames)

            for vname, channels in vanim.items():
                addFrames(vname, {0: channels}, 1, "value", frames)

            for n,frame in frames.items():
                twists = []
                for bname in frame.keys():
                    bframe = frame[bname]
                    tfm = Transform()
                    value = 0.0
                    for key in bframe.keys():
                        if key == "translation":
                            tfm.setTrans(bframe["translation"], prop)
                        elif key == "rotation":
                            tfm.setRot(bframe["rotation"], prop)
                        elif key == "scale":
                            tfm.setScale(bframe["scale"], prop)
                        elif key == "general_scale":
                            tfm.setGeneral(bframe["general_scale"], prop)
                        elif key == "value":
                            value = bframe["value"][0]
                        else:
                            print(" GG ", bname, key)

                    if (bname == "@selection" or
                        bname in KnownRigs):
                        if self.affectObject:
                            tfm.setRna(rig)
                            if self.insertKeys:
                                tfm.insertKeys(rig, None, n+offset, rig.name, self.driven)
                    elif rig.type != 'ARMATURE':
                        continue
                    elif bname in rig.pose.bones.keys():
                        self.transformBone(rig, bname, tfm, value, n, offset, False)
                    elif bname[0:6] == "TWIST-":
                        twists.append((bname[6:], tfm, value))
                    else:
                        if self.affectValues:
                            keys = getRigKeys(bname, rig, props, taken, missing)
                        else:
                            keys = None
                        if keys:
                            for key,factor in keys:
                                setFloatProp(rig, key, factor*float(value))
                                if self.insertKeys:
                                    rig.keyframe_insert('["%s"]' % key, frame=n+offset, group=key)

                for (bname, tfm, value) in twists:
                    self.transformBone(rig, bname, tfm, value, n, offset, True)

                if rig.DazRig == "mhx":
                    for suffix in ["L", "R"]:
                        forearm = rig.pose.bones["forearm.fk."+suffix]
                        hand = rig.pose.bones["hand.fk."+suffix]
                        hand.rotation_euler[1] = forearm.rotation_euler[1]
                        forearm.rotation_euler[1] = 0
                        if self.insertKeys:
                            tfm.insertKeys(rig, forearm, n+offset, bname, self.driven)
                            tfm.insertKeys(rig, hand, n+offset, bname, self.driven)

                if self.usePoseLib:
                    name = os.path.splitext(os.path.basename(filepath))[0]
                    addToPoseLib(rig, name)

            offset += n + 1

        return offset,prop


    def transformBone(self, rig, bname, tfm, value, n, offset, twist):
        from .node import setBoneTransform, setBoneTwist
        from .formula import addPoseboneDriver
        from .driver import isFaceBoneDriven

        pb = rig.pose.bones[bname]
        if False and isFaceBoneDriven(rig, pb):
            if theSettings.verbosity > 4:
                print("Face driven", pb.name)
            pass
        elif pb.bone.select or not self.selectedOnly:
            if self.useDrivers:
                if not self.useTranslations:
                    tfm.noTrans()
                if not self.useRotations:
                    tfm.noRot()
                if not self.useScale:
                    tfm.noScale()
                if not self.useGeneral:
                    tfm.noGeneral()
                if not twist:
                    addPoseboneDriver(scn, rig, pb, tfm, "Poses", errors)
            else:
                if twist:
                    setBoneTwist(tfm, pb)
                else:
                    setBoneTransform(tfm, pb)
                if self.insertKeys:
                    tfm.insertKeys(rig, pb, n+offset, bname, self.driven)


    def findDrivers(self, rig):
        driven = {}
        if (rig.animation_data and
            rig.animation_data.drivers):
            for fcu in rig.animation_data.drivers:
                words = fcu.data_path.split('"')
                if (words[0] == "pose.bones[" and
                    words[2] != "].constraints["):
                    driven[words[1]] = True
        self.driven = list(driven.keys())

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def addToPoseLib(rig, name):
    if rig.pose_library:
        pmarkers = rig.pose_library.pose_markers
        frame = 0
        for pmarker in pmarkers:
            if pmarker.frame >= frame:
                frame = pmarker.frame + 1
    else:
        frame = 0
    bpy.ops.poselib.pose_add(frame=frame)
    pmarker = rig.pose_library.pose_markers.active
    pmarker.name = name
    #for pmarker in rig.pose_library.pose_markers:
    #    print("  ", pmarker.name, pmarker.frame)


def getRigKeys(bname, rig, props, taken, missing):
    from .formula import getOldFormula
    if bname in rig.keys():
        return [(bname,1)]

    lcname = stripKey(bname.lower())

    for prefix in ["ectrlv", "ectrl", "ctrlvsm", "ctrl", "phm", "ephm"]:
        n = len(prefix)        
        if lcname[0:n] == prefix:
            keys = getSynonyms(lcname[n:])
            for key in keys:
                if (key+"l" in props.keys() and
                    key+"r" in props.keys()):
                    taken[key+"l"] = taken[key+"r"] = True
                    left = props[key+"l"]
                    right = props[key+"r"]
                    m = len(left) - len(bname[n:])
                    both = left[0:m-1] + bname[n:]
                    lform = getOldFormula(rig, both, left)
                    rform = getOldFormula(rig, both, right)
                    if lform and rform:
                        return [(left, lform.value), (right, rform.value)]
                    else:
                        print("Missing formula", both, left, right)
                        return [(left,1), (right,-1)]
                elif key in props.keys():
                    if taken[key]:
                        return []
                    else:
                        #taken[key] = True
                        return [(props[key],1)]
            if bname[n:] not in missing:
                missing.append(bname[n:])
    return None


def stripKey(key):                
    if key[-5:] == "_div2":
        key = key[:-5]
    if key[-3:] == "_hd":
        key = key[:-3]
    if key[-2:] == "hd":
        key = key[:-2]
    if key[-4:-1] == "_hd":
        key = key[:-4] + key[-1]
    if key[-3:-1] == "hd":
        key = key[:-3] + key[-1]
    return key
    

def getSynonyms(key):
    synonymList = [
        ["updown", "up-down", "downup", "down-up"],
        ["inout", "in-out", "outin", "out-in"],
        ["cheeks", "cheek"],
    ]
    for synkeys in synonymList:
        for synkey in synkeys:
            if synkey in key:
                return [key] + [key.replace(synkey, syn) for syn in synkeys if syn != synkey]        
    return [key]
    

def getAnimKeys(anim):
    return [key[0:2] for key in anim["keys"]]


def selectAll(rig, select):
    if rig.type != 'ARMATURE':
        return
    selected = []
    for bone in rig.data.bones:
        if bone.select:
            selected.append(bone.name)
        if select == True:
            bone.select = True
        else:
            bone.select = (bone.name in select)
    return selected


def clearAction(self, ob):
    if self.useAction:
        if self.makeNewAction and ob.animation_data:
            ob.animation_data.action = None
    elif self.usePoseLib:
        if self.makeNewPoseLib and ob.pose_library:
            ob.pose_library = None


def nameAction(self, ob, scn):
    if self.useAction:
        if self.makeNewAction and ob.animation_data:
            act = ob.animation_data.action
            if act:
                act.name = self.actionName
    elif self.usePoseLib:
        if self.makeNewPoseLib and ob.pose_library:
            if ob.pose_library:
                ob.pose_library.name = self.poseLibName



class StandardAnimation:

    def getAnimations(self, context):
        import time
        from .main import finishMain
        from .poser import loadPoserAnimation
        from .fileutils import getMultiFiles

        rig = context.object
        scn = context.scene
        if not self.selectedOnly:
            selected = selectAll(rig, True)
        theSettings.forAnimation(self, rig, scn)
        if scn.tool_settings.use_keyframe_insert_auto:
            self.insertKeys = True
        else:
            self.insertKeys = self.useAction
        self.findDrivers(rig)
        clearAction(self, rig)
        missing = []
        startframe = offset = scn.frame_current
        props = []
        t1 = time.clock()
        print("\n--------------------")

        dazfiles = getMultiFiles(self, theDazExtensions)
        poserfiles = getMultiFiles(self, thePoserExtensions)
        nfiles = len(dazfiles) + len(poserfiles)
        if nfiles == 0:
            raise DazError("No corresponding DAZ or Poser file selected")
        self.verbose = (nfiles == 1)

        for filepath in dazfiles:
            print("*", os.path.basename(filepath), offset)
            offset,prop = self.getSingleAnimation(filepath, rig, scn, offset, missing)
            if prop:
                props.append(prop)

        if poserfiles:
            loadPoserAnimation(self, context, poserfiles)

        finishMain(self.filepath, t1)
        scn.frame_current = startframe
        nameAction(self, rig, scn)
        if not self.selectedOnly:
            selectAll(rig, selected)

        if missing and self.reportMissing:
            missing.sort()
            print("Missing morphs:\n  %s" % missing)
            raise DazError(
                "Animation loaded but some morphs were missing.     \n"+
                "See list in terminal window.\n" +
                "Check results carefully.", warning=True)


class DAZ_OT_ImportNodePoses(bpy.types.Operator, AffectOptions, ConvertOptions, ActionOptions, AnimatorBase, StandardAnimation):
    bl_idname = "daz.import_node_poses"
    bl_label = "Import Node Poses"
    bl_description = "Import node poses from native DAZ file(s) (*.duf, *.dsf)"
    bl_options = {'UNDO'}

    loadType = 'NODES'
    verbose = False

    def draw(self, context):
        AffectOptions.draw(self, context)
        ConvertOptions.draw(self, context)
        ActionOptions.draw(self, context)


class DAZ_OT_ImportAction(bpy.types.Operator, AffectOptions, ConvertOptions, ActionOptions, AnimatorBase, StandardAnimation):
    bl_idname = "daz.import_action"
    bl_label = "Import Action"
    bl_description = "Import poses from native DAZ file(s) (*.duf, *.dsf) to action"
    bl_options = {'UNDO'}

    loadType = 'ANIMATIONS'
    verbose = False

    def draw(self, context):
        AffectOptions.draw(self, context)
        ConvertOptions.draw(self, context)
        ActionOptions.draw(self, context)

    def execute(self, context):
        return AnimatorBase.execute(self, context)


class DAZ_OT_ImportPoseLib(bpy.types.Operator, AffectOptions, ConvertOptions, PoseLibOptions, AnimatorBase, StandardAnimation):
    bl_idname = "daz.import_poselib"
    bl_label = "Import Pose Library"
    bl_description = "Import poses from native DAZ file(s) (*.duf, *.dsf) to pose library"
    bl_options = {'UNDO'}

    loadType = 'POSES'
    useDrivers = False
    verbose = False

    def draw(self, context):
        AffectOptions.draw(self, context)
        ConvertOptions.draw(self, context)
        PoseLibOptions.draw(self, context)

    def execute(self, context):
        return AnimatorBase.execute(self, context)


class DAZ_OT_ImportSinglePose(bpy.types.Operator, AffectOptions, ConvertOptions, AnimatorBase, StandardAnimation):
    bl_idname = "daz.import_single_pose"
    bl_label = "Import Pose"
    bl_description = "Import a pose from native DAZ file(s) (*.duf, *.dsf)"
    bl_options = {'UNDO'}

    loadType = 'POSES'
    useDrivers = False
    verbose = False
    useAction = False
    usePoseLib = False

    def draw(self, context):
        AffectOptions.draw(self, context)
        ConvertOptions.draw(self, context)

    def execute(self, context):
        return AnimatorBase.execute(self, context)


def getCommonStart(seq):
    if not seq:
        return ""
    s1, s2 = min(seq), max(seq)
    l = min(len(s1), len(s2))
    if l == 0 :
        return ""
    for i in range(l) :
        if s1[i] != s2[i] :
            return s1[0:i]
    return s1[0:l]

#-------------------------------------------------------------
#   Save current frame
#-------------------------------------------------------------

def actionFrameName(ob, frame):
    return ("%s_%s" % (ob.name, frame))


def findAction(aname):
    for act in bpy.data.actions:
        if act.name == aname:
            return act
    return None


class DAZ_OT_SaveCurrentFrame(bpy.types.Operator):
    bl_idname = "daz.save_current_frame"
    bl_label = "Save Current Frame"
    bl_description = "Save all poses for current frame in new actions"
    bl_options = {'UNDO'}

    def execute(self, context):
        try:
            self.saveCurrentFrame(context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}


    def saveCurrentFrame(self, context):
        scn = context.scene
        frame = scn.frame_current
        for ob in getSceneObjects(context):
            if ob.hide_select:
                continue
            aname = actionFrameName(ob, frame)
            act = findAction(aname)
            if act:
                act.use_fake_user = False
                bpy.data.actions.remove(act)
            if ob.animation_data:
                ob.animation_data.action = None
            ob.keyframe_insert("location", frame=frame)
            ob.keyframe_insert("rotation_euler", frame=frame)
            ob.keyframe_insert("scale", frame=frame)
            for key in dir(ob):
                if (key[0:2] == "Dz" or
                    key[0:3] in ["Daz", "Mha", "Mhh"]):
                    value = getattr(ob, key)
                    if (isinstance(value, int) or
                        isinstance(value, float) or
                        isinstance(value, bool) or
                        isinstance(value, str)):
                        ob[key] = value
            for key in ob.keys():
                try:
                    ob.keyframe_insert(key, frame=frame)
                except TypeError:
                    pass
            if ob.type == 'ARMATURE':
                tfm = Transform()
                for pb in ob.pose.bones:
                    tfm.insertKeys(ob, pb, frame, pb.name, [])
        scn.frame_current += 10
        for ob in getSceneObjects(context):
            if ob.animation_data:
                act = ob.animation_data.action
                if act:
                    act.use_fake_user = True
                    act.name = actionFrameName(ob, frame)
                ob.animation_data.action = None
            if ob.type == 'ARMATURE':
                for pb in ob.pose.bones:
                    pb.location = (0,0,0)
                    pb.rotation_euler = (0,0,0)
                    pb.rotation_quaternion = (1,0,0,0)
                    pb.scale = (1,1,1)


class DAZ_OT_RestoreCurrentFrame(bpy.types.Operator):
    bl_idname = "daz.restore_current_frame"
    bl_label = "Restore Current Frame"
    bl_description = "Restore all poses for current frame from stored actions"
    bl_options = {'UNDO'}

    def execute(self, context):
        try:
            self.restoreCurrentFrame(context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}


    def restoreCurrentFrame(self, context):
        scn = context.scene
        frame = scn.frame_current
        for ob in getSceneObjects(context):
            if ob.hide_select:
                continue
            aname = actionFrameName(ob, frame)
            act = findAction(aname)
            if act:
                if ob.animation_data is None:
                    ob.animation_data_create()
                ob.animation_data.action = act
            else:
                print("Missing action %s" % aname)
        updateScene(context)
        scn.frame_current += 1
        scn.frame_current -= 1
        for ob in getSceneObjects(context):
            if ob.animation_data:
                ob.animation_data.action = None
        return{'FINISHED'}

#----------------------------------------------------------
#   Clear action
#----------------------------------------------------------

class DAZ_OT_PruneAction(bpy.types.Operator):
    bl_idname = "daz.prune_action"
    bl_label = "Prune Action"
    bl_description = "Remove F-curves with a single zero key"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.animation_data and ob.animation_data.action)

    def execute(self, context):
        try:
            self.pruneAction(context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}

    def pruneAction(self, context):
        act = context.object.animation_data.action
        deletes = []
        for fcu in act.fcurves:
            kpts = fcu.keyframe_points 
            if len(kpts) == 0:
                deletes.append(fcu)
            elif len(kpts) == 1:
                if fcu.data_path == "scale":
                    default = 1
                else:
                    default = 0
                if kpts[0].co[1] == default:
                    deletes.append(fcu)
        for fcu in deletes:
            act.fcurves.remove(fcu)

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ImportNodePoses,
    DAZ_OT_ImportAction,
    DAZ_OT_ImportPoseLib,
    DAZ_OT_ImportSinglePose,
    DAZ_OT_SaveCurrentFrame,
    DAZ_OT_RestoreCurrentFrame,
    DAZ_OT_PruneAction,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
