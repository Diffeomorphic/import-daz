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

from mathutils import *
from .utils import *

class Transform:
    def __init__(self, trans=None, rot=None, scale=None, general=None):
        self.trans = trans
        self.rot = rot
        self.scale = scale
        self.general = general

        self.transProp = None
        self.rotProp = None
        self.scaleProp = None
        self.generalProp = None

    def __repr__(self):
        return ("<TFM t:%s\n    r::%s\n    s:%s\n    g:%s\n    %s %s %s %s>" %
                (self.trans, self.rot, self.scale, self.general,
                 self.transProp, self.rotProp, self.scaleProp, self.generalProp))


    def noTrans(self):
        self.trans = None
        self.transProp = None

    def setTrans(self, trans, prop=None):
        self.trans = Vector(trans)
        self.transProp = prop

    def noRot(self):
        self.rot = None
        self.rotProp = None

    def setRot(self, rot, prop=None):
        self.rot = Vector(rot)
        self.rotProp = prop

    def noScale(self):
        self.scale = None
        self.scaleProp = None

    def setScale(self, scale, prop=None):
        self.scale = Vector(scale)
        self.scaleProp = prop

    def noGeneral(self):
        self.general = None
        self.generalProp = None

    def setGeneral(self, general, prop=None):
        self.general = Vector(general)
        self.generalProp = prop
        print("GGG", self.general)


    def evalTrans(self):
        if self.trans is None:
            return Vector((0,0,0))
        else:
            return d2b00(self.trans)

    def evalRot(self):
        if self.rot is None:
            return Vector((0,0,0))
        else:
            return self.rot*D

    def evalScale(self):
        if self.scale is None:
            scale = Vector((1,1,1))
        else:
            scale = self.scale
        if self.general is not None:
            scale *= self.general
        return scale


    def getTransMat(self):
        return Matrix.Translation(self.evalTrans())


    def getRotMat(self, pb):
        if self.rot is None:
            return Matrix()
        elif isinstance(self.rot, Quaternion):
            mat = self.rot.to_matrix()
        elif isinstance(self.rot, Matrix):
            mat = self.rot
        else:
            mat = Euler(Vector(self.rot)*D, pb.DazRotMode).to_matrix()
        return mat.to_4x4()


    def getScaleMat(self):
        mat = Matrix()
        scale = self.evalScale()
        for n in range(3):
            mat[n][n] = scale[n]
        return mat


    def setRna(self, rna):
        rna.location = d2b(self.evalTrans())
        rot = d2bu(self.evalRot())
        rna.rotation_euler = rot
        if hasattr(rna, "rotation_quaternion"):
            rna.rotation_quaternion = Euler(rot).to_quaternion()
        rna.scale = d2bs(self.evalScale())


    def clearRna(self, rna):
        rna.location = (0,0,0)
        rna.rotation_euler = (0,0,0)
        if hasattr(rna, "rotation_quaternion"):
            rna.rotation_quaternion = (1,0,0,0)
        rna.scale = (1,1,1)


    def insertKeys(self, rig, pb, frame, group, driven):
        self.insertTranslationKey(rig, pb, frame, group, driven)
        self.insertRotationKey(rig, pb, frame, group, driven)
        self.insertScaleKey(rig, pb, frame, group, driven)


    def insertTranslationKey(self, rig, pb, frame, group, driven):
        if self.trans is None:
            return
        if pb is None:
            rig.keyframe_insert("location", frame=frame, group=group)
            return
        if pb.bone.use_connect or pb.name in driven:
            return
        if (pb.lock_location[0] == False or
            pb.lock_location[1] == False or
            pb.lock_location[2] == False):
            pb.keyframe_insert("location", frame=frame, group=group)


    def insertRotationKey(self, rig, pb, frame, group, driven):
        if self.rot is None:
            return
        if pb is None:
            rig.keyframe_insert("rotation_euler", frame=frame, group=group)
            return
        if pb.name in driven:
            return
        if pb.rotation_mode == 'QUATERNION':
            channel = "rotation_quaternion"
        else:
            channel = "rotation_euler"
        pb.keyframe_insert(channel, frame=frame, group=group)


    def insertScaleKey(self, rig, pb, frame, group, driven):
        if self.scale is None and self.general is None:
            return
        if pb is None:
            rig.keyframe_insert("scale", frame=frame, group=group)
            return
        if pb.name in driven:
            return
        if (pb.lock_scale[0] == False or
            pb.lock_scale[1] == False or
            pb.lock_scale[2] == False):
            pb.keyframe_insert("scale", frame=frame, group=group)


