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



"""
Abstract

Postprocessing of rigify rig

"""

import bpy
import os
from collections import OrderedDict
from bpy.props import *
from mathutils import Vector

from .error import DazError, handleDazError
from .utils import *

R_FACE = 1
R_DEFORM = 29
R_HELP = 30


def setupTables(meta):
    global MetaBones, MetaParents, MetaDisconnect, RigifyParams
    global RigifySkeleton, GenesisCarpals, GenesisSpine
    global Genesis3Spine, Genesis3Mergers, Genesis3Parents
    global Genesis3Toes, Genesis3Renames, Carpals
    global DeformBones

    if meta.DazPre278:
        hips = "hips"
        spine = "spine"
        spine1 = "spine-1"
        chest = "chest"
        chest1 = "chest-1"
        neck = "neck"
        head = "head"
        rigtype = "rigify"

        MetaBones = {
            "spine" : spine,
            "spine-1" : spine1,
            "chest" : chest,
            "chest-1" : chest1,
            "chestUpper" : chest1,
            "neck" : neck,
            "head" : head,
        }

        RigifyParams = {}

        DeformBones = {
            "neckLower" : "DEF-neck",
            "neckUpper" : "DEF-neck",
            "ShldrBend" : "DEF-upper_arm.01.%s",
            "ForearmBend" : "DEF-forearm.01.%s",
            "ThighBend" : "DEF-thigh.01.%s",
            "ShldrTwist" : "DEF-upper_arm.02.%s",
            "ForearmTwist" : "DEF-forearm.02.%s",
            "ThighTwist" : "DEF-thigh.02.%s",
            "Shin" : "DEF-shin.02.%s",
        }

    else:
        hips = "spine"
        spine = "spine.001"
        spine1 = "spine.002"
        chest = "spine.003"
        chest1 = "spine.004"
        neck = "spine.005"
        if meta.DazUseSplitNeck:
            neck1= "spine.006"
            head = "spine.007"
        else:
            head = "spine.006"
        rigtype = "rigify2"
        bpy.ops.object.mode_set(mode='EDIT')
        eb = meta.data.edit_bones[head]
        deleteChildren(eb, meta)
        bpy.ops.object.mode_set(mode='OBJECT')

        MetaBones = {
            "spine" : hips,
            "spine-1" : spine1,
            "chest" : chest,
            "chest-1" : chest1,
            "chestUpper" : chest1,
            "neck" : neck,
            "head" : head,
        }

        RigifyParams = {
            ("spine", "neck_pos", 6),
            ("spine", "pivot_pos", 1),
        }

        DeformBones = {
            "neckLower" : "DEF-spine.005",
            "neckUpper" : "DEF-spine.006",
            "ShldrBend" : "DEF-upper_arm.%s",
            "ForearmBend" : "DEF-forearm.%s",
            "ThighBend" : "DEF-thigh.%s",
            "ShldrTwist" : "DEF-upper_arm.%s.001",
            "ForearmTwist" : "DEF-forearm.%s.001",
            "ThighTwist" : "DEF-thigh.%s.001",
            "Shin" : "DEF-shin.%s.001",
        }


    MetaDisconnect = [hips, neck]

    MetaParents = {
        "breast.L" : chest,
        "breast.R" : chest,
        "shoulder.L" : chest1,
        "shoulder.R" : chest1,
    }

    RigifySkeleton = {
    hips :            ("hip", ["hip", "pelvis"]),

    "thigh.L" :         "lThigh",
    "shin.L" :          "lShin",
    "foot.L" :          "lFoot",
    "toe.L" :           "lToe",

    "thigh.R" :         "rThigh",
    "shin.R" :          "rShin",
    "foot.R" :          "rFoot",
    "toe.R" :           "rToe",

    "abdomen" :         "abdomen",
    "chest" :           "chest",
    "neck" :            "neck",
    "head" :            "head",

    "shoulder.L" :      "lCollar",
    "upper_arm.L" :     "lShldr",
    "forearm.L" :       "lForeArm",
    "hand.L" :          "lHand",

    "shoulder.R" :      "rCollar",
    "upper_arm.R" :     "rShldr",
    "forearm.R" :       "rForeArm",
    "hand.R" :          "rHand",

    "thumb.01.L" :       "lThumb1",
    "thumb.02.L" :       "lThumb2",
    "thumb.03.L" :       "lThumb3",
    "f_index.01.L" :     "lIndex1",
    "f_index.02.L" :     "lIndex2",
    "f_index.03.L" :     "lIndex3",
    "f_middle.01.L" :    "lMid1",
    "f_middle.02.L" :    "lMid2",
    "f_middle.03.L" :    "lMid3",
    "f_ring.01.L" :      "lRing1",
    "f_ring.02.L" :      "lRing2",
    "f_ring.03.L" :      "lRing3",
    "f_pinky.01.L" :     "lPinky1",
    "f_pinky.02.L" :     "lPinky2",
    "f_pinky.03.L" :     "lPinky3",

    "thumb.01.R" :       "rThumb1",
    "thumb.02.R" :       "rThumb2",
    "thumb.03.R" :       "rThumb3",
    "f_index.01.R" :     "rIndex1",
    "f_index.02.R" :     "rIndex2",
    "f_index.03.R" :     "rIndex3",
    "f_middle.01.R" :    "rMid1",
    "f_middle.02.R" :    "rMid2",
    "f_middle.03.R" :    "rMid3",
    "f_ring.01.R" :      "rRing1",
    "f_ring.02.R" :      "rRing2",
    "f_ring.03.R" :      "rRing3",
    "f_pinky.01.R" :     "rPinky1",
    "f_pinky.02.R" :     "rPinky2",
    "f_pinky.03.R" :     "rPinky3",

    "palm.01.L" :       "lCarpal1",
    "palm.02.L" :       "lCarpal2",
    "palm.03.L" :       "lCarpal3",
    "palm.04.L" :       "lCarpal4",

    "palm.01.R" :       "rCarpal1",
    "palm.02.R" :       "rCarpal2",
    "palm.03.R" :       "rCarpal3",
    "palm.04.R" :       "rCarpal4",
    }

    BreastBones = {
    "breast.L" :        "lPectoral",
    "breast.R" :        "rPectoral",
    #"breastDrv.L" :     "lPectoralDrv",
    #"breastDrv.R" :     "rPectoralDrv",
    }
    if meta.DazUseBreasts:
        RigifySkeleton = addDicts([RigifySkeleton, BreastBones])


    GenesisCarpals = {
    "palm.01.L" :        (("lCarpal1", "lIndex1"), ["lCarpal1"]),
    "palm.02.L" :        (("lCarpal1", "lMid1"), []),
    "palm.03.L" :        (("lCarpal2", "lRing1"), ["lCarpal2"]),
    "palm.04.L" :        (("lCarpal2", "lPinky1"), []),

    "palm.01.R" :        (("rCarpal1", "rIndex1"), ["rCarpal1"]),
    "palm.02.R" :        (("rCarpal1", "rMid1"), []),
    "palm.03.R" :        (("rCarpal2", "rRing1"), ["rCarpal2"]),
    "palm.04.R" :        (("rCarpal2", "rPinky1"), []),

    }

    GenesisSpine = [
    ("abdomen", spine, hips),
    ("abdomen2", spine1, spine),
    ("chest", chest, spine1),
    ("neck", neck, chest),
    ("head", head, neck),
    ]

    Genesis3Spine = [
    ("abdomen", spine, hips),
    ("abdomen2", spine1, spine),
    ("chest", chest, spine1),
    ("chestUpper", chest1, chest),
    ("neck", neck, chest1),
    ]
    if meta.DazUseSplitNeck:
        Genesis3Spine += [
            ("neckUpper", neck1, neck),
            ("head", head, neck1)]
    else:
        Genesis3Spine.append(("head", head, neck))

    Genesis3Mergers = {
    "lShldrBend" : ["lShldrTwist"],
    "lForearmBend" : ["lForearmTwist"],
    "lThighBend" : ["lThighTwist"],
    "lFoot" : ["lMetatarsals"],

    "rShldrBend" : ["rShldrTwist"],
    "rForearmBend" : ["rForearmTwist"],
    "rThighBend" : ["rThighTwist"],
    "rFoot" : ["rMetatarsals"],
    }
    if not meta.DazUseSplitNeck:
        Genesis3Mergers["neckLower"] = ["neckUpper"]

    Genesis3Parents = {
    "neckLower" : "chestUpper",
    "chestUpper" : "chestLower",
    "chestLower" : "abdomenUpper",
    "abdomenUpper" : "abdomenLower",
    "lForearmBend" : "lShldrBend",
    "lHand" : "lForearmBend",
    "lShin" : "lThighBend",
    "lToe" : "lFoot",
    "rForearmBend" : "rShldrBend",
    "rHand" : "rForearmBend",
    "rShin" : "rThighBend",
    "rToe" : "rFoot",
    }
    if meta.DazUseSplitNeck:
        Genesis3Parents["head"] = "neckUpper"
        Genesis3Parents["neckUpper"] = "neckLower"
    else:
        Genesis3Parents["head"] = "neckLower"

    Genesis3Toes = {
    "lBigToe" : "lToe",
    "lSmallToe1" : "lToe",
    "lSmallToe2" : "lToe",
    "lSmallToe3" : "lToe",
    "lSmallToe4" : "lToe",
    "rBigToe" : "rToe",
    "rSmallToe1" : "rToe",
    "rSmallToe2" : "rToe",
    "rSmallToe3" : "rToe",
    "rSmallToe4" : "rToe",
    }

    Genesis3Renames = {
    "abdomenLower" : "abdomen",
    "abdomenUpper" : "abdomen2",
    "chestLower" : "chest",
    "neckLower" : "neck",
    "lShldrBend" : "lShldr",
    "lForearmBend" : "lForeArm",
    "lThighBend" : "lThigh",
    "rShldrBend" : "rShldr",
    "rForearmBend" : "rForeArm",
    "rThighBend" : "rThigh",
    }

    return rigtype, hips, head


Carpals = {
    "Carpal1" : "Index1",
    "Carpal2" : "Mid1",
    "Carpal3" : "Ring1",
    "Carpal4" : "Pinky1",
}


def deleteChildren(eb, meta):
    for child in eb.children:
        deleteChildren(child, meta)
        meta.data.edit_bones.remove(child)


def renameBones(rig, bones):
    bpy.ops.object.mode_set(mode='EDIT')
    for dname,rname in bones.items():
        eb = rig.data.edit_bones[dname]
        eb.name = rname
    bpy.ops.object.mode_set(mode='OBJECT')


class DazBone:
    def __init__(self, eb):
        self.name = eb.name
        self.head = eb.head.copy()
        self.tail = eb.tail.copy()
        self.roll = eb.roll
        if eb.parent:
            self.parent = eb.parent.name
        else:
            self.parent = None
        self.use_deform = eb.use_deform
        self.rotation_mode = None

    def getPose(self, pb):
        self.rotation_mode = pb.rotation_mode
        self.lock_location = pb.lock_location
        self.lock_rotation = pb.lock_rotation

    def setPose(self, pb):
        pb.rotation_mode = self.rotation_mode
        pb.lock_location = self.lock_location
        pb.lock_rotation = self.lock_rotation


def addDicts(structs):
    joined = {}
    for struct in structs:
        for key,value in struct.items():
            joined[key] = value
    return joined


def setupDazSkeleton(meta):
    rigifySkel = RigifySkeleton
    if meta.DazRigifyType in ["genesis1", "genesis2"]:
        rigifySkel["chestUpper"] = "chestUpper"
        rigifySkel["abdomen2"] = "abdomen2"
        spineBones = Genesis3Spine
    elif meta.DazRigifyType in ["genesis3", "genesis8"]:
        spineBones = Genesis3Spine

    dazskel = {}
    for rbone, dbone in rigifySkel.items():
        if isinstance(dbone, tuple):
            dbone = dbone[0]
        if isinstance(dbone, str):
            dazskel[dbone] = rbone
    return rigifySkel, spineBones, dazskel


def reparentBones(rig, parents):
    bpy.ops.object.mode_set(mode='EDIT')
    for bname,pname in parents.items():
        if (pname in rig.data.edit_bones.keys() and
            bname in rig.data.edit_bones.keys()):
            eb = rig.data.edit_bones[bname]
            parb = rig.data.edit_bones[pname]
            eb.use_connect = False
            eb.parent = parb
    bpy.ops.object.mode_set(mode='OBJECT')


def setupExtras(rig, rigifySkel, spineBones):
    extras = OrderedDict()
    taken = []
    for dbone,_rbone,_pbone in spineBones:
        taken.append(dbone)
    for _rbone, dbone in rigifySkel.items():
        if isinstance(dbone, tuple):
            dbone = dbone[0]
            if isinstance(dbone, tuple):
                dbone = dbone[0]
        taken.append(dbone)
    for ob in rig.children:
        for vgrp in ob.vertex_groups:
            if (vgrp.name not in taken and
                vgrp.name in rig.data.bones.keys()):
                extras[vgrp.name] = vgrp.name
    for dbone in list(extras.keys()):
        bone = rig.data.bones[dbone]
        while bone.parent:
            pname = bone.parent.name
            if pname in extras.keys() or pname in taken:
                break
            extras[pname] = pname
            bone = bone.parent
    return extras


def fixCarpals(rig):
    if "lCarpal3" in rig.data.bones.keys():
        return
    bpy.ops.object.mode_set(mode='EDIT')
    for prefix in ["l", "r"]:
        for bname in ["Carpal1", "Carpal2"]:
            if prefix+bname in rig.data.edit_bones.keys():
                eb = rig.data.edit_bones[prefix+bname]
                rig.data.edit_bones.remove(eb)
        hand = rig.data.edit_bones[prefix+"Hand"]
        hand.tail = 2*hand.tail - hand.head
        for bname,cname in Carpals.items():
            if prefix+cname in rig.data.edit_bones.keys():
                eb = rig.data.edit_bones.new(prefix+bname)
                child = rig.data.edit_bones[prefix+cname]
                eb.head = hand.head
                eb.tail = child.head
                eb.roll = child.roll
                eb.parent = hand
                child.parent = eb
                child.use_connect = True
    bpy.ops.object.mode_set(mode='OBJECT')
    for ob in rig.children:
        if ob.type == 'MESH':
            for prefix in ["l", "r"]:
                for vgrp in ob.vertex_groups:
                    if vgrp.name == prefix+"Carpal2":
                        vgrp.name = prefix+"Carpal4"


def splitBone(rig, bname, upname):
    if upname in rig.data.bones.keys():
        return
    bpy.ops.object.mode_set(mode='EDIT')
    eblow = rig.data.edit_bones[bname]
    vec = eblow.tail - eblow.head
    mid = eblow.head + vec/2
    ebup = rig.data.edit_bones.new(upname)
    for eb in eblow.children:
        eb.parent = ebup
    ebup.head = mid
    ebup.tail = eblow.tail
    ebup.parent = eblow
    ebup.roll = eblow.roll
    eblow.tail = mid
    bpy.ops.object.mode_set(mode='OBJECT')


def splitNeck(meta):
    bpy.ops.object.mode_set(mode='EDIT')
    spine = meta.data.edit_bones["spine"]
    spine3 = meta.data.edit_bones["spine.003"]
    bonelist={}
    bpy.ops.armature.select_all(action='DESELECT')
    spine3.select = True
    bpy.ops.armature.subdivide()
    spinebones = spine.children_recursive_basename
    chainlength = len(spinebones)
    for x in range(chainlength):
        y = str(x)
        spinebones[x].name = "spine" + "." + y
    for x in range(chainlength):
        y = str(x+1)
        spinebones[x].name = "spine" + ".00" + y
    bpy.ops.armature.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')


def deleteIfNotExist(bnames, rig, meta, context):
    setActiveObject(context, meta)
    bpy.ops.object.mode_set(mode='EDIT')
    for dname,mname in bnames:
        if (dname not in rig.data.bones.keys() and
            mname in meta.data.edit_bones.keys()):
            eb = meta.data.edit_bones[mname]
            meta.data.edit_bones.remove(eb)
    bpy.ops.object.mode_set(mode='OBJECT')
    setActiveObject(context, rig)


def checkRigifyEnabled(context):
    for addon in context.user_preferences.addons:
        if addon.module == "rigify":
            return True
    return False


def getRigifyBone(bname, dazSkel, extras, spineBones):
    global DeformBones
    if bname in DeformBones:
        return DeformBones[bname]
    if bname[1:] in DeformBones:
        prefix = bname[0]
        return (DeformBones[bname[1:]] % prefix.upper())
    if bname in dazSkel.keys():
        rname = dazSkel[bname]
        if rname in MetaBones.keys():
            return "DEF-" + MetaBones[rname]
        else:
            return "DEF-" + rname
    elif bname in extras.keys():
        return extras[bname]
    else:
        for dname,rname,pname in spineBones:
            if dname == bname:
                return "DEF-" + rname
    print("MISS", bname)
    return None


def getDazBones(rig):
    # Setup info about DAZ bones
    dazBones = OrderedDict()
    bpy.ops.object.mode_set(mode='EDIT')
    for eb in rig.data.edit_bones:
        dazBones[eb.name] = DazBone(eb)
    bpy.ops.object.mode_set(mode='POSE')
    for pb in rig.pose.bones:
        dazBones[pb.name].getPose(pb)

    bpy.ops.object.mode_set(mode='OBJECT')
    return dazBones


def createMeta(context):
    from collections import OrderedDict
    from .mhx import connectToParent, unhideAllObjects
    from .figure import getRigType
    from .merge import mergeBonesAndVgroups
    from .fix import fixPelvis, fixHands

    print("Create metarig")
    rig = context.object
    scale = rig.DazScale
    scn = context.scene
    if not(rig and rig.type == 'ARMATURE'):
        raise DazError("Rigify: %s is neither an armature nor has armature parent" % ob)

    unhideAllObjects(context, rig)

    # Create metarig
    bpy.ops.object.mode_set(mode='OBJECT')
    try:
        bpy.ops.object.armature_human_metarig_add()
    except AttributeError:
        raise DazError("The Rigify add-on is not enabled. It is found under rigging.")
    bpy.ops.object.location_clear()
    bpy.ops.object.rotation_clear()
    bpy.ops.object.scale_clear()
    bpy.ops.transform.resize(value=(100*scale, 100*scale, 100*scale))
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    meta = context.object
    cns = meta.constraints.new('COPY_SCALE')
    cns.name = "Rigify Source"
    cns.target = rig
    cns.mute = True

    meta.DazPre278 = ("hips" in meta.data.bones.keys())
    meta.DazRigifyType = getRigType(rig)
    meta.DazUseBreasts = (not meta.DazPre278 and rig.data.DazExtraDrivenBones)
    meta.DazUseSplitNeck = (not meta.DazPre278 and meta.DazRigifyType in ["genesis3", "genesis8"])
    if meta.DazUseSplitNeck:
        splitNeck(meta)
    meta.DazRigType,hips,head = setupTables(meta)

    activateObject(context, rig)
    setSelected(rig, True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    if meta.DazRigifyType in ["genesis1", "genesis2"]:
        fixPelvis(rig)
        fixCarpals(rig)
        splitBone(rig, "chest", "chestUpper")
        splitBone(rig, "abdomen", "abdomen2")
        delbones = [
            ("lPectoral", "breast.L"),
            ("rPectoral", "breast.R"),
        ]
        deleteIfNotExist(delbones, rig, meta, context)
    elif meta.DazRigifyType in ["genesis3", "genesis8"]:
        mergeBonesAndVgroups(rig, Genesis3Mergers, Genesis3Parents, context)
        reparentBones(rig, Genesis3Toes)
        renameBones(rig, Genesis3Renames)
    else:
        activateObject(context, meta)
        deleteObject(context, meta)
        raise DazError("Cannot rigify %s %s" % (meta.DazRigifyType, rig.name))

    connectToParent(rig)
    rigifySkel, spineBones, dazSkel = setupDazSkeleton(meta)
    dazBones = getDazBones(rig)

    # Fit metarig to default DAZ rig
    setActiveObject(context, meta)
    setSelected(meta, True)
    bpy.ops.object.mode_set(mode='EDIT')

    for eb in meta.data.edit_bones:
        eb.use_connect = False

    for eb in meta.data.edit_bones:
        try:
            dname = rigifySkel[eb.name]
        except KeyError:
            dname = None
        if isinstance(dname, tuple):
            dname,_vgrps = dname
        if isinstance(dname, str):
            if dname in dazBones.keys():
                dbone = dazBones[dname]
                eb.head = dbone.head
                eb.tail = dbone.tail
                eb.roll = dbone.roll
        elif isinstance(dname, tuple):
            if (dname[0] in dazBones.keys() and
                dname[1] in dazBones.keys()):
                dbone1 = dazBones[dname[0]]
                dbone2 = dazBones[dname[1]]
                eb.head = dbone1.head
                eb.tail = dbone2.head

    hip = meta.data.edit_bones[hips]
    dbone = dazBones["hip"]
    hip.tail = Vector((1,2,3))
    hip.head = dbone.tail
    hip.tail = dbone.head

    if meta.DazRigifyType in ["genesis3", "genesis8"]:
        eb = meta.data.edit_bones[head]
        eb.tail = eb.head + 1.0*(eb.tail - eb.head)

    fixHands(meta)

    for suffix in [".L", ".R"]:
        shoulder = meta.data.edit_bones["shoulder"+suffix]
        upperarm = meta.data.edit_bones["upper_arm"+suffix]
        shin = meta.data.edit_bones["shin"+suffix]
        foot = meta.data.edit_bones["foot"+suffix]
        toe = meta.data.edit_bones["toe"+suffix]

        vec = shoulder.tail - shoulder.head
        if (upperarm.head - shoulder.tail).length < 0.02*vec.length:
            shoulder.tail -= 0.02*vec

        if "pelvis"+suffix in meta.data.edit_bones.keys():
            thigh = meta.data.edit_bones["thigh"+suffix]
            pelvis = meta.data.edit_bones["pelvis"+suffix]
            pelvis.head = hip.head
            pelvis.tail = thigh.head

        #if "breast"+suffix in meta.data.edit_bones.keys():
        #    breast = meta.data.edit_bones["breast"+suffix]
        #    breast.head[0] = breast.tail[0]
        #    breast.head[2] = breast.tail[2]

        foot.head = shin.tail
        toe.head = foot.tail
        xa,ya,za = foot.head
        xb,yb,zb = toe.head

        heelhead = foot.head
        heeltail = Vector((xa, yb-1.3*(yb-ya), zb))
        mid = (toe.head + heeltail)/2
        r = Vector((yb-ya,0,0))
        if xa > 0:
            fac = 0.3
        else:
            fac = -0.3
        heel02head = mid + fac*r
        heel02tail = mid - fac*r

        if "heel"+suffix in meta.data.edit_bones.keys():
            heel = meta.data.edit_bones["heel"+suffix]
            heel.head = heelhead
            heel.tail = heeltail
        if "heel.02"+suffix in meta.data.edit_bones.keys():
            heel02 = meta.data.edit_bones["heel.02"+suffix]
            heel02.head = heel02head
            heel02.tail = heel02tail

    for eb in meta.data.edit_bones:
        if (eb.parent and
            eb.head == eb.parent.tail and
            eb.name not in MetaDisconnect):
            eb.use_connect = True

    # Fix spine
    mbones = meta.data.edit_bones
    for dname,rname,pname in spineBones:
        if dname not in dazBones.keys():
            continue
        dbone = dazBones[dname]
        if rname in mbones.keys():
            eb = mbones[rname]
        else:
            eb = mbones.new(dname)
            eb.name = rname
        eb.use_connect = False
        eb.head = dbone.head
        eb.tail = dbone.tail
        eb.roll = dbone.roll
        eb.parent = mbones[pname]
        eb.use_connect = True
        eb.layers = list(eb.parent.layers)

    reparentBones(meta, MetaParents)

    # Add rigify properties to spine bones
    bpy.ops.object.mode_set(mode='OBJECT')
    for _dname,rname,_pname in spineBones:
        pb = meta.pose.bones[rname]
        if "rigify_type" in pb.keys():
            #print("%s: %s" % (rname, pb["rigify_type"]))
            if pb["rigify_type"] == "spines.super_head":
                pb["rigify_type"] = ""
        else:
            pb["rigify_type"] = ""

    for rname,prop,value in RigifyParams:
        if rname in meta.pose.bones:
            pb = meta.pose.bones[rname]
            setattr(pb.rigify_parameters, prop, value)

    print("Metarig created")
    return meta


def rigifyMeta(context):
    from .driver import getBoneDrivers, copyDriver, changeBoneTarget, changeDriverTarget
    from .node import setParent, clearParent
    from .daz import copyPropGroups
    from .fix import fixCorrectives, checkCorrectives, fixCustomShape
    from .mhx import unhideAllObjects
    from .figure import copyBoneInfo

    print("Rigify metarig")
    meta = context.object
    rig = None
    for cns in meta.constraints:
        if cns.type == 'COPY_SCALE' and cns.name == "Rigify Source":
            rig = cns.target

    if rig is None:
        raise DazError("Original rig not found")
    unhideAllObjects(context, rig)
    if not inSceneLayer(context, rig):
        showSceneLayer(context, rig)

    bpy.ops.object.mode_set(mode='POSE')
    for pb in meta.pose.bones:
        if hasattr(pb, "rigify_parameters"):
            if hasattr (pb.rigify_parameters, "roll_alignment"):
                pb.rigify_parameters.roll_alignment = "manual"            

    try:
        bpy.ops.pose.rigify_generate()
    except:
        raise DazError("Cannot rigify %s rig %s    " % (meta.DazRigifyType, rig.name))

    scn = context.scene
    gen = context.object
    coll = getCollection(context)
    print("Fix generated rig", gen.name)

    setActiveObject(context, rig)
    rigifySkel, spineBones, dazSkel = setupDazSkeleton(meta)
    dazBones = getDazBones(rig)

    empty = bpy.data.objects.new("Widgets", None)
    coll.objects.link(empty)
    empty.parent = gen
    for ob in getSceneObjects(context):
        if ob.parent is None and ob.name[0:4] == "WGT-":
            ob.parent = empty

    extras = setupExtras(rig, rigifySkel, spineBones)
    if meta.DazUseBreasts:
        for prefix in ["l", "r"]:
            extras[prefix+"PectoralDrv"] = prefix+"PectoralDrv"

    driven = {}
    for pb in rig.pose.bones:
        fcus = getBoneDrivers(rig, pb)
        if fcus:
            driven[pb.name] = fcus

    # Add extra bones to generated rig
    faceLayers = R_FACE*[False] + [True] + (31-R_FACE)*[False]
    helpLayers = R_HELP*[False] + [True] + (31-R_HELP)*[False]
    setActiveObject(context, gen)
    bpy.ops.object.mode_set(mode='EDIT')
    for dname,rname in extras.items():
        if dname not in dazBones.keys():
            continue
        dbone = dazBones[dname]
        eb = gen.data.edit_bones.new(rname)
        eb.head = dbone.head
        eb.tail = dbone.tail
        eb.roll = dbone.roll
        eb.use_deform = dbone.use_deform
        if eb.use_deform:
            eb.layers = faceLayers
            eb.layers[R_DEFORM] = True
        else:
            eb.layers = helpLayers
        if dname in driven.keys():
            eb.layers = helpLayers

    # Add parents to extra bones
    for dname,rname in extras.items():
        if dname not in dazBones.keys():
            continue
        dbone = dazBones[dname]
        eb = gen.data.edit_bones[rname]
        if dbone.parent:
            pname = getRigifyBone(dbone.parent, dazSkel, extras, spineBones)
            if (pname in gen.data.edit_bones.keys()):
                eb.parent = gen.data.edit_bones[pname]
                eb.use_connect = (eb.parent != None and eb.parent.tail == eb.head)
            else:
                print("No parent", dbone.name, dbone.parent, pname)
                bones = list(dazSkel.keys())
                bones.sort()
                print("Bones:", bones)
                msg = ("Bone %s has no parent %s" % (dbone.name, dbone.parent))
                raise DazError(msg)

    if meta.DazUseBreasts:
        for prefix,suffix in [("l", ".L"), ("r", ".R")]:
            db = gen.data.edit_bones[prefix + "PectoralDrv"]
            eb = gen.data.edit_bones["breast" + suffix]
            db.parent = eb.parent
            eb.parent = db

    bpy.ops.object.mode_set(mode='POSE')

    # Lock extras
    for dname,rname in extras.items():
        if dname not in dazBones.keys():
            continue
        if rname in gen.pose.bones.keys():
            pb = gen.pose.bones[rname]
            dazBones[dname].setPose(pb)

    # Remove breast custom shapes, because they are placed differently in Daz
    for rname in ["breast.L", "breast.R"]:
        if rname in gen.pose.bones.keys():
            pb = gen.pose.bones[rname]
            pb.custom_shape = None

    # Rescale custom shapes
    if meta.DazRigifyType in ["genesis3", "genesis8"]:
        fixCustomShape(gen, ["head", "spine_fk.007"], 4)
    if bpy.app.version >= (2,82,0):
        fixCustomShape(gen, ["chest"], 1, Vector((0,-100*rig.DazScale,0)))

    # Add DAZ properties
    for key in rig.keys():
        gen[key] = rig[key]
    for key in rig.data.keys():
        gen.data[key] = rig.data[key]

    for bname,dname in rigifySkel.items():
        if dname in rig.data.bones.keys():
            bone = rig.data.bones[dname]
            if bname in gen.data.bones.keys():
                rbone = gen.data.bones[bname]
                copyBoneInfo(bone, rbone)
            else:
                words = bname.split(".")
                if len(words) == 2:
                    gname,suffix = words
                    if gname+"_fk."+suffix in gen.data.bones.keys():
                        fkbone = gen.data.bones[gname+"_fk."+suffix]
                    elif gname+".fk."+suffix in gen.data.bones.keys():
                        fkbone = gen.data.bones[gname+".fk."+suffix]
                    else:
                        fkbone = None
                    if fkbone:
                        copyBoneInfo(bone, fkbone)

    # Handle bone parents
    boneParents = []
    for ob in rig.children:
        if ob.parent_type == 'BONE':
            boneParents.append((ob, ob.parent_bone))
            clearParent(ob)

    for ob,dname in boneParents:
        rname = getRigifyBone(dname, dazSkel, extras, spineBones)
        if rname and rname in gen.data.bones.keys():
            print("Parent %s to bone %s" % (ob.name, rname))
            bone = gen.data.bones[rname]
            setParent(context, ob, gen, bone.name)
        else:
            print("Did not find bone parent %s %s" %(dname, rname))
            setParent(context, ob, gen, None)

    # Copy DAZ morph drivers and change armature modifier
    activateObject(context, gen)
    for ob in rig.children:
        if ob.type == 'MESH':
            ob.parent = gen

            for dname,rname,_pname in spineBones:
                if dname in ob.vertex_groups.keys():
                    vgrp = ob.vertex_groups[dname]
                    vgrp.name = "DEF-" + rname

            for rname,dname in rigifySkel.items():
                if dname[1:] in ["Thigh", "Shin", "Shldr", "ForeArm"]:
                    rigifySplitGroup(rname, dname, ob, rig, True, meta)
                elif (meta.DazPre278 and
                      dname[1:] in ["Thumb1", "Index1", "Mid1", "Ring1", "Pinky1"]):
                    rigifySplitGroup(rname, dname, ob, rig, False, meta)
                elif isinstance(dname, str):
                    if dname in ob.vertex_groups.keys():
                        vgrp = ob.vertex_groups[dname]
                        vgrp.name = "DEF-" + rname
                else:
                    mergeVertexGroups(rname, dname[1], ob)

            for dname,rname in extras.items():
                if dname in ob.vertex_groups.keys():
                    vgrp = ob.vertex_groups[dname]
                    vgrp.name = rname

            if ob.animation_data:
                for fcu in ob.animation_data.drivers:
                    changeDriverTarget(fcu, gen)

            if ob.data.animation_data:
                for fcu in ob.data.animation_data.drivers:
                    changeDriverTarget(fcu, gen)

            if ob.data.shape_keys and ob.data.shape_keys.animation_data:
                for fcu in ob.data.shape_keys.animation_data.drivers:
                    changeDriverTarget(fcu, gen)

            for mod in ob.modifiers:
                if mod.type == 'ARMATURE' and mod.object == rig:
                    mod.object = gen

    # Add generated rig to group
    group = None
    if bpy.app.version <= (2,80,0):
        for grp in bpy.data.groups:
            if rig.name in grp.objects:
                group = grp
                break
        print("Group: %s" % group)
    if group:
        group.objects.link(gen)

    # Fix drivers
    assoc = [(rigi,daz) for (daz,rigi,_) in Genesis3Spine]
    assoc += [(rigi,daz) for (rigi,daz) in RigifySkeleton.items()]
    for bname, fcus in driven.items():
        if bname in gen.pose.bones.keys():
            if bname not in gen.pose.bones.keys():
                continue
            pb = gen.pose.bones[bname]
            copyPropGroups(rig, gen, pb)
            for fcu in fcus:
                fcu2 = copyDriver(fcu, pb, gen)
                changeBoneTarget(fcu2, assoc)

    # Fix correctives
    assoc = [("ORG-"+rigi,daz) for (rigi,daz) in assoc]
    fixCorrectives(gen, assoc)
    checkCorrectives(gen)

    #Clean up
    setattr(gen.data, DrawType, 'STICK')
    setattr(gen, ShowXRay, True)
    gen.DazRig = meta.DazRigType
    name = rig.name
    activateObject(context, rig)
    deleteObject(context, rig)
    if scn.DazDeleteMeta:
        activateObject(context, meta)
        deleteObject(context, meta)
    activateObject(context, gen)
    gen.name = name
    bpy.ops.object.mode_set(mode='POSE')
    print("Rigify created")
    return gen


def rigifySplitGroup(rname, dname, ob, rig, before, meta):
    from .fix import splitVertexGroup
    if dname not in ob.vertex_groups.keys():
        return
    bone = rig.data.bones[dname]
    if before:
        if meta.DazPre278:
            bendname = "DEF-" + rname[:-2] + ".01" + rname[-2:]
            twistname = "DEF-" + rname[:-2] + ".02" + rname[-2:]
        else:
            bendname = "DEF-" + rname
            twistname = "DEF-" + rname + ".001"
    else:
        bendname = "DEF-" + rname + ".01"
        twistname = "DEF-" + rname + ".02"
    splitVertexGroup(ob, dname, bendname, twistname, bone.head_local, bone.tail_local)


def mergeVertexGroups(rname, dnames, ob):
    if not (dnames and
            dnames[0] in ob.vertex_groups.keys()):
        return
    vgrp = ob.vertex_groups[dnames[0]]
    vgrp.name = "DEF-" + rname


def setBoneName(bone, gen):
    fkname = bone.name.replace(".", ".fk.")
    if fkname in gen.data.bones.keys():
        gen.data.bones[fkname]
        bone.fkname = fkname
        bone.ikname = fkname.replace(".fk.", ".ik")

    defname = "DEF-" + bone.name
    if defname in gen.data.bones.keys():
        gen.data.bones[defname]
        bone.realname = defname
        return

    defname1 = "DEF-" + bone.name + ".01"
    if defname in gen.data.bones.keys():
        gen.data.bones[defname1]
        bone.realname1 = defname1
        bone.realname2 = defname1.replace(".01.", ".02.")
        return

    defname1 = "DEF-" + bone.name.replace(".", ".01.")
    if defname in gen.data.bones.keys():
        gen.data.bones[defname1]
        bone.realname1 = defname1
        bone.realname2 = defname1.replace(".01.", ".02")
        return

    if bone.name in gen.data.bones.keys():
        gen.data.edit_bones[bone.name]
        bone.realname = bone.name

#-------------------------------------------------------------
#  Buttons
#-------------------------------------------------------------

class DAZ_OT_RigifyDaz(bpy.types.Operator):
    bl_idname = "daz.rigify_daz"
    bl_label = "Convert To Rigify"
    bl_description = "Convert active rig to rigify"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and not ob.DazRigifyType)

    def execute(self, context):
        try:
            self.rigifyDaz(context)
        except DazError as err:
            print("\nError when rigifying Daz rig:    \n%s" % err)
            handleDazError(context)
        return{'FINISHED'}


    def rigifyDaz(self, context):
        import time
        t1 = time.clock()
        print("Modifying DAZ rig to Rigify")
        rig = context.object
        rname = rig.name
        createMeta(context)
        gen = rigifyMeta(context)
        t2 = time.clock()
        print("DAZ rig %s successfully rigified in %.3f seconds" % (rname, t2-t1))


class DAZ_OT_CreateMeta(bpy.types.Operator):
    bl_idname = "daz.create_meta"
    bl_label = "Create Metarig"
    bl_description = "Create a metarig from the active rig"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and not ob.DazRigifyType)

    def execute(self, context):
        try:
            createMeta(context)
        except DazError as err:
            handleDazError(context)
        return{'FINISHED'}


class DAZ_OT_RigifyMetaRig(bpy.types.Operator):
    bl_idname = "daz.rigify_meta"
    bl_label = "Rigify Metarig"
    bl_description = "Convert metarig to rigify"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.DazRigifyType)

    def execute(self, context):
        try:
            rigifyMeta(context)
        except DazError as err:
            handleDazError(context)
        return{'FINISHED'}

#-------------------------------------------------------------
#   Rigify action
#-------------------------------------------------------------

def rigifyAction(act):
    print("RA", act)
    pass

#-------------------------------------------------------------
#   List bones
#-------------------------------------------------------------

def listBones(context):
    rig = context.object
    if not (rig and rig.type == 'ARMATURE'):
        msg = ("Not an armature:   \n'%s'       " % rig)
        raise DazError(msg)
    print("Bones in %s:" % rig.name)
    for pb in rig.pose.bones:
        print('    "%s" : ("", "%s"),' % (pb.name, pb.rotation_mode))


class DAZ_OT_ListBones(bpy.types.Operator):
    bl_idname = "daz.list_bones"
    bl_label = "List Bones"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'ARMATURE')

    def execute(self, context):
        try:
            listBones(context)
        except DazError as err:
            print("Error when listing bones: %s" % err)
            handleDazError(context)
        return{'FINISHED'}

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_RigifyDaz,
    DAZ_OT_CreateMeta,
    DAZ_OT_RigifyMetaRig,
    DAZ_OT_ListBones,
]

def initialize():
    bpy.types.Object.DazRigifyType = StringProperty(default="")
    bpy.types.Object.DazRigType = StringProperty(default="")
    bpy.types.Object.DazUseBreasts = BoolProperty(default=False)
    bpy.types.Object.DazUseSplitNeck = BoolProperty(default=False)
    bpy.types.Object.DazPre278 = BoolProperty(default=False)

    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
