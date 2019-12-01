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
import math
from mathutils import *
from .asset import *
from .utils import *
from .transform import Transform
from .settings import theSettings
from .error import *
from .node import Node, Instance

#-------------------------------------------------------------
#   RotateRoll
#-------------------------------------------------------------

RotateRoll = {
    "lPectoral" : -90,
    "rPectoral" : 90,

    "upperJaw" : -90,
    "lowerJaw" : -90,

    "lFoot" : -90,
    "lMetatarsals" : -90,
    "lToe" : -90,

    "rFoot" : 90,
    "rMetatarsals" : 90,
    "rToe" : 90,

    "lShldr" : 90,
    "lShldrBend" : 90,
    "lShldrTwist" : 90,
    "lForeArm" : 0,
    "lForearmBend" : 90,
    "lForearmTwist" : 90,

    "rShldr" : -90,
    "rShldrBend" : -90,
    "rShldrTwist" : -90,
    "rForeArm" : 0,
    "rForearmBend" : -90,
    "rForearmTwist" : -90,
}

ZPerpendicular = {
    "lShldr" : 2,
    "lShldrBend" : 2,
    "lShldrTwist" : 2,
    "lForeArm" : 2,
    "lForearmBend" : 2,
    "lForearmTwist" : 2,

    "rShldr" : 2,
    "rShldrBend" : 2,
    "rShldrTwist" : 2,
    "rForeArm" : 2,
    "rForearmBend" : 2,
    "rForearmTwist" : 2,

    "lThigh" : 0,
    "lThighBend" : 0,
    "lThighTwist" : 0,
    "lShin" : 0,
    "lFoot" : 0,
    "lMetatarsals" : 0,
    "lToe" : 0,

    "rThigh" : 0,
    "rThighBend" : 0,
    "rThighTwist" : 0,
    "rShin" : 0,
    "rFoot" : 0,
    "rMetatarsals" : 0,
    "rToe" : 0,
}

RotationMode = {
    "lShin" :       'YZX',
    "lFoot" :       'YZX',
    "lMetatarsals" :'YZX',
    "lToe" :        'YZX',

    "lBigToe" :     'YZX',
    "lBigToe_2" :   'YZX',
    "lSmallToe1" :  'YZX',
    "lSmallToe1_2" :'YZX',
    "lSmallToe2" :  'YZX',
    "lSmallToe2_2" :'YZX',
    "lSmallToe3" :  'YZX',
    "lSmallToe3_2" :'YZX',
    "lSmallToe4" :  'YZX',
    "lSmallToe4_2" :'YZX',

    "rShin" :       'YZX',
    "rFoot" :       'YZX',
    "rMetatarsals" :'YZX',
    "rToe" :        'YZX',

    "rBigToe" :     'YZX',
    "rBigToe_2" :   'YZX',
    "rSmallToe1" :  'YZX',
    "rSmallToe1_2" :'YZX',
    "rSmallToe2" :  'YZX',
    "rSmallToe2_2" :'YZX',
    "rSmallToe3" :  'YZX',
    "rSmallToe3_2" :'YZX',
    "rSmallToe4" :  'YZX',
    "rSmallToe4_2" :'YZX',

    "abdomen" :     'YZX',
    "abdomenUpper" : 'YZX',
    "abdomenLower" : 'YZX',
    "abdomen2" :    'YZX',
    "chest" :       'YZX',
    "chestLower" :  'YZX',
    "chestUpper" :  'YZX',
    "neck" :        'YZX',
    "neckLower" :   'YZX',
    "neckUpper" :   'YZX',
    "head" :        'YZX',

    "lEye" :        'YZX',
    "rEye" :        'YZX',
    "lowerFaceRig" :'YZX',
    "lowerJaw" :    'YZX',
    "upperJaw" :    'YZX',

    "lEye" :        'YZX',
    "rEye" :        'YZX',
    "upperJaw" :    'YZX',
    "lowerJaw" :    'YZX',
    "tongueBase" :  'YZX',
    "tongue01" :    'YZX',
    "tongue02" :    'YZX',
    "tongue03" :    'YZX',
    "tongue04" :    'YZX',
    "tongue05" :    'YZX',
    "tongueTip" :   'YZX',

    "lForeArm" :    'YZX',
    "lForearmBend" : 'YZX',
    "lForearmTwist" : 'YZX',
    "lHand" :       'YZX',
    "lCarpal1" :    'YZX',
    "lCarpal2" :    'YZX',
    "lCarpal3" :    'YZX',
    "lCarpal4" :    'YZX',

    "rForeArm" :    'YZX',
    "rForearmBend" : 'YZX',
    "rForearmTwist" : 'YZX',
    "rHand" :       'YZX',
    "rCarpal1" :    'YZX',
    "rCarpal2" :    'YZX',
    "rCarpal3" :    'YZX',
    "rCarpal4" :    'YZX',

    "lThumb1" :     'YZX',
    "lThumb2" :     'YZX',
    "lThumb3" :     'YZX',
    "lIndex1" :     'YZX',
    "lIndex2" :     'YZX',
    "lIndex3" :     'YZX',
    "lMid1" :       'YZX',
    "lMid2" :       'YZX',
    "lMid3" :       'YZX',
    "lRing1" :      'YZX',
    "lRing2" :      'YZX',
    "lRing3" :      'YZX',
    "lPinky1" :     'YZX',
    "lPinky2" :     'YZX',
    "lPinky3" :     'YZX',

    "rThumb1" :     'YZX',
    "rThumb2" :     'YZX',
    "rThumb3" :     'YZX',
    "rIndex1" :     'YZX',
    "rIndex2" :     'YZX',
    "rIndex3" :     'YZX',
    "rMid1" :       'YZX',
    "rMid2" :       'YZX',
    "rMid3" :       'YZX',
    "rRing1" :      'YZX',
    "rRing2" :      'YZX',
    "rRing3" :      'YZX',
    "rPinky1" :     'YZX',
    "rPinky2" :     'YZX',
    "rPinky3" :     'YZX',
}

BoneAlternatives = {
    "abdomen" : "abdomenLower",
    "abdomen2" : "abdomenUpper",
    "chest" : "chestLower",
    "chest_2" : "chestUpper",
    "neck" : "neckLower",
    "neck_2" : "neckUpper",

    "lShldr" : "lShldrBend",
    "lForeArm" : "lForearmBend",
    "lWrist" : "lForearmTwist",
    "lCarpal2-1" : "lCarpal2",
    "lCarpal2" : "lCarpal4",

    "rShldr" : "rShldrBend",
    "rForeArm" : "rForearmBend",
    "rWrist" : "rForearmTwist",
    "rCarpal2-1" : "rCarpal2",
    "rCarpal2" : "rCarpal4",

    "upperJaw" : "upperTeeth",
    "tongueBase" : "tongue01",
    "tongue01" : "tongue02",
    "tongue02" : "tongue03",
    "tongue03" : "tongue04",
    "MidBrowUpper" : "CenterBrow",

    "lLipCorver" : "lLipCorner",
    "lCheekLowerInner" : "lCheekLower",
    "lCheekUpperInner" : "lCheekUpper",
    "lEyelidTop" : "lEyelidUpper",
    "lEyelidLower_2" : "lEyelidLowerInner",
    "lNoseBirdge" : "lNasolabialUpper",

    "rCheekLowerInner" : "rCheekLower",
    "rCheekUpperInner" : "rCheekUpper",

    "lThigh" : "lThighBend",
    "lBigToe2" : "lBigToe_2",

    "rThigh" : "rThighBend",
    "rBigToe2" : "rBigToe_2",

    "Shaft 1" : "shaft1",
    "Shaft 2" : "shaft2",
    "Shaft 3" : "shaft3",
    "Shaft 4" : "shaft4",
    "Shaft 5" : "shaft5",
    "Shaft5" : "shaft5",
    "Shaft 6" : "shaft6",
    "Shaft 7" : "shaft7",
    "Left Testicle" : "lTesticle",
    "Right Testicle" : "rTesticle",
    "Scortum" : "scrotum",
    "Legs Crease" : "legsCrease",
    "Rectum" : "rectum1",
    "Rectum 1" : "rectum1",
    "Rectum 2" : "rectum2",
    "Colon" : "colon",
    "Root" : "shaftRoot",
    "root" : "shaftRoot",
}


ArmBones = [
    "lShldr", "lShldrBend", "lShldrTwist",
    "lForeArm", "lForearmBend", "lForearmTwist",

    "rShldr", "rShldrBend", "rShldrTwist",
    "rForeArm", "rForearmBend", "rForearmTwist",
]

LegBones = [
    "lThigh", "lThighBend", "lThighTwist",
    "lShin", "lFoot", "lMetatarsals", "lToe",

    "rThigh", "rThighBend", "rThighTwist",
    "rShin", "rFoot", "rMetatarsals", "rToe",
]

FingerBones = [
    "lHand",
    "lCarpal1", "lCarpal2", "lCarpal3", "lCarpal4",
    "lIndex1", "lIndex2", "lIndex3",
    "lMid1", "lMid2", "lMid3",
    "lRing1", "lRing2", "lRing3",
    "lPinky1", "lPinky2", "lPinky3",

    "rHand",
    "rCarpal1", "rCarpal2", "rCarpal3", "rCarpal4",
    "rIndex1", "rIndex2", "rIndex3",
    "rMid1", "rMid2", "rMid3",
    "rRing1", "rRing2", "rRing3",
    "rPinky1", "rPinky2", "rPinky3",
]

ToeBones = [
    "lBigToe", "lSmallToe1", "lSmallToe2", "lSmallToe3", "lSmallToe4",
    "lBigToe_2", "lSmallToe1_2", "lSmallToe2_2", "lSmallToe3_2", "lSmallToe4_2",

    "rBigToe", "rSmallToe1", "rSmallToe2", "rSmallToe3", "rSmallToe4",
    "rBigToe_2", "rSmallToe1_2", "rSmallToe2_2", "rSmallToe3_2", "rSmallToe4_2",
]

Planes = {
    "lShldr" : ("lArm", ""),
    "lForeArm" : ("lArm", ""),
    "lHand" : ("", "lHand"),
    "lCarpal1" : ("", "lHand"),
    "lCarpal2" : ("", "lHand"),
    "lCarpal3" : ("", "lHand"),
    "lCarpal4" : ("", "lHand"),
    "lThumb1" : ("lThumb", ""),
    "lThumb2" : ("lThumb", ""),
    "lThumb3" : ("lThumb", ""),
    "lIndex1" : ("lIndex", "lHand"),
    "lIndex2" : ("lIndex", "lHand"),
    "lIndex3" : ("lIndex", "lHand"),
    "lMid1" : ("lMid", "lHand"),
    "lMid2" : ("lMid", "lHand"),
    "lMid3" : ("lMid", "lHand"),
    "lRing1" : ("lRing", "lHand"),
    "lRing2" : ("lRing", "lHand"),
    "lRing3" : ("lRing", "lHand"),
    "lPinky1" : ("lPinky", "lHand"),
    "lPinky2" : ("lPinky", "lHand"),
    "lPinky3" : ("lPinky", "lHand"),

    "rShldr" : ("rArm", ""),
    "rForeArm" : ("rArm", ""),
    "rHand" : ("", "rHand"),
    "rCarpal1" : ("", "rHand"),
    "rCarpal2" : ("", "rHand"),
    "rCarpal3" : ("", "rHand"),
    "rCarpal4" : ("", "rHand"),
    "rThumb1" : ("rThumb", ""),
    "rThumb2" : ("rThumb", ""),
    "rThumb3" : ("rThumb", ""),
    "rIndex1" : ("rIndex", "rHand"),
    "rIndex2" : ("rIndex", "rHand"),
    "rIndex3" : ("rIndex", "rHand"),
    "rMid1" : ("rMid", "rHand"),
    "rMid2" : ("rMid", "rHand"),
    "rMid3" : ("rMid", "rHand"),
    "rRing1" : ("rRing", "rHand"),
    "rRing2" : ("rRing", "rHand"),
    "rRing3" : ("rRing", "rHand"),
    "rPinky1" : ("rPinky", "rHand"),
    "rPinky2" : ("rPinky", "rHand"),
    "rPinky3" : ("rPinky", "rHand"),
}


def getTargetName(bname, targets):
    bname = bname.replace("%20", " ")
    if bname in targets.keys():
        return bname
    elif (bname in BoneAlternatives.keys() and
          BoneAlternatives[bname] in targets.keys()):
        return BoneAlternatives[bname]
    else:
        return None

#-------------------------------------------------------------
#   BoneInstance
#-------------------------------------------------------------

class BoneInstance(Instance):

    def __init__(self, fileref, node, struct):
        from .figure import FigureInstance
        Instance.__init__(self, fileref, node, struct)
        if isinstance(self.parent, FigureInstance):
            self.figure = self.parent
        elif isinstance(self.parent, BoneInstance):
            self.figure = self.parent.figure


    def __repr__(self):
        pname = (self.parent.id if self.parent else None)
        fname = (self.figure.name if self.figure else None)
        return "<BoneInst %s N: %s F: %s P: %s R:%s>" % (self.id, self.node.name, fname, pname, self.rna)


    def listBones(self):
        self.figure.bones[self.node.name] = self
        for child in self.children.values():
            if isinstance(child, BoneInstance):
                child.listBones()


    def parentObject(self, context):
        pass


    def buildExtra(self):
        pass


    def getHeadTail(self, cscale, center, fitfile):
        if fitfile:
            head = cscale*(self.previewAttrs["center_point"] - center)
            tail = cscale*(self.previewAttrs["end_point"] - center)
        else:
            head = cscale*(self.attributes["center_point"] - center)
            tail = cscale*(self.attributes["end_point"] - center)
        if (tail-head).length < 1e-4:
            tail = head + Vector((0,0,1e-4))
        return head,tail


    def buildPose(self, figure, inFace, targets, missing):
        from .node import setBoneTransform
        from .driver import isBoneDriven

        node = self.node
        rig = figure.rna
        if node.name not in rig.pose.bones.keys():
            return
        pb = rig.pose.bones[node.name]
        self.rna = pb
        if isBoneDriven(rig, pb):
            pb.rotation_mode = node.rotDaz
            pb.bone.layers = [False,True] + 30*[False]
        else:
            try:
                pb.rotation_mode = RotationMode[pb.name]
            except KeyError:
                pb.rotation_mode = 'QUATERNION'
        pb.DazRotMode = node.rotDaz
        #pb.rotation_mode = node.rotDaz

        tname = getTargetName(node.name, targets)
        if tname:
            tinst = targets[tname]
            tfm = Transform(
                trans = tinst.attributes["translation"],
                rot = tinst.attributes["rotation"])
            tchildren = tinst.children
        else:
            tinst = None
            tfm = Transform(
                trans = self.attributes["translation"],
                rot = self.attributes["rotation"])
            tchildren = {}

        setBoneTransform(tfm, pb)

        if theSettings.useLockRot:
            self.setRotationLock(pb)
        if theSettings.useLockLoc:
            self.setLocationLock(pb)

        for child in self.children.values():
            if isinstance(child, BoneInstance):
                child.buildPose(figure, inFace, tchildren, missing)


    def formulate(self, key, value):
        from .node import setBoneTransform
        if self.figure is None:
            return
        channel,comp = key.split("/")
        self.attributes[channel][getIndex(comp)] = value
        pb = self.rna
        node = self.node
        tfm = Transform(
            trans=self.attributes["translation"],
            rot=self.attributes["rotation"])
        setBoneTransform(tfm, pb)


    def setRotationLock(self, pb):
        pb.lock_rotation = (False,False,False)
        if self.node.name[-5:] == "Twist":
            pb.lock_rotation = (True,False,True)
        #elif self.name[-4:] == "Bend":
        #    pb.lock_rotation = (False,True,False)
        pb.DazRotLocks = pb.lock_rotation


    def setLocationLock(self, pb):
        pb.lock_location = (False,False,False)
        if (pb.parent and
            pb.parent.name not in ["upperFaceRig", "lowerFaceRig"]):
            pb.lock_location = (True,True,True)
        pb.DazLocLocks = pb.lock_location

    '''
    def setRotationLock1(self, pb):
        locks = [False, False, False]
        limits = [None, None, None]
        useLimits = False
        for idx,comp in enumerate(self.rotation):
            xyz = IndexComp[idx]
            if "locked" in comp.keys() and comp["locked"]:
                locks[idx] = True
            elif "clamped"in comp.keys() and comp["clamped"]:
                if comp["min"] == 0 and comp["max"] == 0:
                    locks[idx] = True
                else:
                    limits[idx] = (comp["min"], comp["max"])
                    useLimits = True
        for idx,lock in enumerate(locks):
            pb.lock_rotation[idx] = lock
        if theSettings.useLimitRot and useLimits:
            cns = pb.constraints.new('LIMIT_ROTATION')
            cns.owner_space = 'LOCAL'
            for idx,limit in enumerate(limits):
                if limit is not None:
                    mind, maxd = limit
                    setattr(cns, "use_limit_%s" % xyz, True)
                    setattr(cns, "min_%s" % xyz, mind*D)
                    setattr(cns, "max_%s" % xyz, maxd*D)


    def setLocationLock1(self, pb):
        locks = [False, False, False]
        limits = [None, None, None]
        useLimits = False
        for idx,comp in enumerate(self.rotation):
            xyz = IndexComp[idx]
            if "locked" in comp.keys() and comp["locked"]:
                locks[idx] = True
            elif "clamped"in comp.keys() and comp["clamped"]:
                if comp["min"] == 0 and comp["max"] == 0:
                    locks[idx] = True
                else:
                    limits[idx] = (comp["min"], comp["max"])
                    useLimits = True
        for idx,lock in enumerate(locks):
            pb.lock_rotation[idx] = lock
        if theSettings.useLimitLoc and useLimits:
            cns = pb.constraints.new('LIMIT_LOCATION')
            cns.owner_space = 'LOCAL'
            for idx,limit in enumerate(limits):
                if limit is not None:
                    mind, maxd = limit
                    setattr(cns, "use_min_%s" % xyz, True)
                    setattr(cns, "use_max_%s" % xyz, True)
                    setattr(cns, "min_%s" % xyz, mind*D)
                    setattr(cns, "max_%s" % xyz, maxd*D)
    '''

#-------------------------------------------------------------
#   Bone
#-------------------------------------------------------------

class Bone(Node):

    def __init__(self, fileref):
        Node.__init__(self, fileref)
        self.roll = 0.0
        self.useRoll = False
        self.translation = []
        self.rotation = []


    def __repr__(self):
        return ("<Bone %s %s>" % (self.id, self.rna))


    def getSelfId(self):
        return self.node.name


    def makeInstance(self, fileref, struct):
        return BoneInstance(fileref, self, struct)


    def getInstance(self, caller, ref, strict=True):
        iref = instRef(ref)
        try:
            return self.instances[iref]
        except KeyError:
            pass
        try:
            return self.instances[BoneAlternatives[iref]]
        except KeyError:
            pass
        if (theSettings.verbosity <= 2 and
            len(self.instances.values()) > 0):
            return list(self.instances.values())[0]
        msg = ("Did not find instance %s in %s" % (iref, list(self.instances.keys())))
        if theSettings.verbosity > 3:
            reportError(msg)
        else:
            print(msg)
        return None


    def parse(self, struct):
        from .figure import Figure
        Node.parse(self, struct)
        for channel,data in struct.items():
            if channel == "rotation":
                self.rotation = data
            elif channel == "translation":
                self.translation = data
        if isinstance(self.parent, Figure):
            self.figure = self.parent
        elif isinstance(self.parent, Bone):
            self.figure = self.parent.figure


    def build(self, context, inst=None):
        pass


    def preprocess(self, context, inst):
        pass


    def postprocess(self, context, inst):
        pass


    def pose(self, context, inst):
        pass


    def getRna(self):
        rig = self.rna
        if rig and self.name in rig.pose.bones.keys():
            return rig.pose.bones[self.name]
        else:
            return None


    def buildEdit(self, figure, rig, parent, inst, cscale, center, fitfile):
        if self.name in rig.data.edit_bones.keys():
            eb = rig.data.edit_bones[self.name]
        else:
            head,tail = inst.getHeadTail(cscale, center, fitfile)
            eb = rig.data.edit_bones.new(self.name)
            figure.bones[self.name] = eb.name
            eb.parent = parent

            eb.head = d2b(head)
            eb.tail = d2b(tail)
            if self.useRoll:
                eb.roll = self.roll
            else:
                self.findRoll(inst, eb, figure)
            self.roll = eb.roll
            self.useRoll = True
            if theSettings.useConnect and parent:
                dist = parent.tail - eb.head
                if dist.length < 1e-4*theSettings.scale:
                    eb.use_connect = True

        for child in inst.children.values():
            if isinstance(child, BoneInstance):
                child.node.buildEdit(figure, rig, eb, child, cscale, center, fitfile)


    units = [Vector((1,0,0)), Vector((0,1,0)), Vector((0,0,1))]

    posRotators = [
        Matrix.Rotation(-math.pi/2, 4, 'Z'),
        Matrix(),
        Matrix.Rotation(math.pi/2, 4, 'X'),
    ]

    negRotators = [
        Matrix.Rotation(math.pi/2, 4, 'Z'),
        Matrix.Rotation(math.pi, 4, 'X'),
        Matrix.Rotation(-math.pi/2, 4, 'X'),
    ]

    def buildOrientation(self, rig, inst, useBest):
        if self.name not in rig.data.edit_bones.keys():
            return
        eb = rig.data.edit_bones[self.name]
        orient = Vector(inst.attributes["orientation"])
        mat = Euler(orient*D, 'XYZ').to_matrix()
        if useBest:
            vec = eb.tail - eb.head
            projs = []
            for n in range(3):
                proj = vec.dot(Mult2(mat, self.units[n]))
                projs.append((abs(proj), (proj<0), n))
            projs.sort()
            _,neg,idx = projs[2]
            if neg:
                rmat = self.negRotators[idx]
            else:
                rmat = self.posRotators[idx]
            mat = Mult2(rmat, mat.to_4x4())
        else:
            mat = mat.to_4x4()
        mat.col[3] = eb.matrix.col[3]
        eb.matrix = mat
        for child in inst.children.values():
            if isinstance(child, BoneInstance):
                child.node.buildOrientation(rig, child, useBest)


    def buildBoneProps(self, rig, inst, cscale, center, fitfile):
        if self.name not in rig.data.bones.keys():
            return
        bone = rig.data.bones[self.name]
        bone.use_inherit_scale = self.inherits_scale
        bone.DazOrientation = inst.attributes["orientation"]

        head,tail = inst.getHeadTail(cscale, center, fitfile)
        head0,tail0 = inst.getHeadTail(cscale, center, False)
        bone.DazHead = head
        bone.DazTail = tail
        bone.DazAngle = 0

        vec = d2b00(tail) - d2b00(head)
        vec0 = d2b00(tail0) - d2b00(head0)
        if vec.length > 0 and vec0.length > 0:
            vec /= vec.length
            vec0 /= vec0.length
            sprod = vec.dot(vec0)
            if sprod < 0.99:
                bone.DazAngle = math.acos(sprod)
                bone.DazNormal = vec.cross(vec0)

        for child in inst.children.values():
            if isinstance(child, BoneInstance):
                child.node.buildBoneProps(rig, child, cscale, center, fitfile)


    def buildFormulas(self, rig, inst):
        from .formula import buildBoneFormula
        if (self.formulas and
            self.name in rig.pose.bones.keys()):
            pb = rig.pose.bones[self.name]
            pb.rotation_mode = self.rotDaz
            errors = []
            buildBoneFormula(self, rig, pb, errors)
        for child in inst.children.values():
            if isinstance(child, BoneInstance):
                child.node.buildFormulas(rig, child)


    def findRoll(self, inst, eb, figure):
        from .merge import GenesisToes
        if (self.getRollFromPlane(inst, eb, figure)):
            return

        if self.name in RotateRoll.keys():
            rr = RotateRoll[self.name]
        elif self.name in GenesisToes["lToe"]:
            rr = -90
        elif self.name in GenesisToes["rToe"]:
            rr = 90
        elif self.name in FingerBones:
            if figure.rigtype == "genesis8":
                if self.name[0] == "l":
                    rr = 90
                else:
                    rr = -90
            else:
                rr = 180
        else:
            rr = 0

        nz = -1
        if self.name in ArmBones:
            nz = 2
        elif self.name in LegBones+ToeBones+FingerBones:
            nz = 0

        eb.roll = rr*D
        if nz >= 0:
            mat = eb.matrix.copy()
            mat[nz][2] = 0
            mat.normalize()
            eb.matrix = mat


    def getRollFromPlane(self, inst, eb, figure):
        try:
            xplane,zplane = Planes[eb.name]
        except KeyError:
            return False
        if (zplane and
            zplane in inst.figure.planes.keys() and
            (figure.rigtype in ["genesis3", "genesis8"] or
             not xplane)):
            zaxis = inst.figure.planes[zplane]
            setRoll(eb, zaxis)
            eb.roll += math.pi/2
            return True
        elif (xplane and
              xplane in inst.figure.planes.keys()):
            xaxis = inst.figure.planes[xplane]
            setRoll(eb, xaxis)
            return True
        else:
            return False


def setRoll(eb, xaxis):
    yaxis = eb.tail - eb.head
    yaxis.normalize()
    xaxis -= yaxis.dot(xaxis)*yaxis
    xaxis.normalize()
    zaxis = xaxis.cross(yaxis)
    zaxis.normalize()
    eb.roll = getRoll(xaxis, yaxis, zaxis)


def getRoll(xaxis, yaxis, zaxis):
    mat = Matrix().to_3x3()
    mat.col[0] = xaxis
    mat.col[1] = yaxis
    mat.col[2] = zaxis
    return getRollFromQuat(mat.to_quaternion())


def getRollFromQuat(quat):
    if abs(quat.w) < 1e-4:
        roll = math.pi
    else:
        roll = 2*math.atan(quat.y/quat.w)
    return roll
