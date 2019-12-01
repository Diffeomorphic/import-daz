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
##

import bpy
import collections

from .asset import Asset
from .utils import *
from .error import *
from .settings import theSettings
from .formula import Formula

#-------------------------------------------------------------
#   External access
#-------------------------------------------------------------

def parseModifierAsset(asset, struct):
    if "skin" in struct.keys():
        return asset.parseTypedAsset(struct, SkinBinding)
    elif "legacy_skin" in struct.keys():
        return asset.parseTypedAsset(struct, LegacySkinBinding)
    elif "morph" in struct.keys():
        return asset.parseTypedAsset(struct, Morph)
    elif "formulas" in struct.keys():
        return asset.parseTypedAsset(struct, FormulaAsset)
    elif "dform" in struct.keys():
        return asset.parseTypedAsset(struct, DForm)
    elif "extra" in struct.keys():
        return parseExtra(asset, struct)
    elif "channel" in struct.keys():
        channel = struct["channel"]
        if channel["type"] == "alias":
            return asset.parseTypedAsset(struct, Alias)
        else:
            return asset.parseTypedAsset(struct, Channel)
    else:
        #print("WARNING: Modifier asset %s not implemented" % asset.fileref)
        #asset = Modifier(asset.fileref)
        raise NotImplementedError("Modifier asset not implemented in file %s:\n  %s" %
            (asset.fileref, list(struct.keys())))


#-------------------------------------------------------------
#   Modifier Assets
#-------------------------------------------------------------

class Modifier(Asset):
    def __repr__(self):
        return ("<Modifier %s %s>" % (self.id, self.type))

    def addModifier(self, inst):
        pass

    def postbuild(self, context, inst):
        pass


class DForm(Modifier):
    def __repr__(self):
        return ("<Dform %s %s>" % (self.id, self.type))

#-------------------------------------------------------------
#   Extra
#-------------------------------------------------------------

def parseExtra(asset, struct):
    extra = struct["extra"]
    if isinstance(extra, list):
        first = extra[0]
    else:
        first = extra

    return asset.parseTypedAsset(struct, ExtraAsset)


class ExtraAsset(Modifier):
    def __init__(self, fileref):
        Modifier.__init__(self, fileref)
        self.extra = None
        self.rest = []

    def __repr__(self):
        return ("<Extra %s %s>" % (self.id, self.type))

    def parse(self, struct):
        Modifier.parse(self, struct)
        extra = struct["extra"]
        if isinstance(extra, list):
            self.extra = extra[0]
            self.rest = extra[1:]
        else:
            self.extra = extra
            self.rest = []

#-------------------------------------------------------------
#   Channel
#-------------------------------------------------------------

class Channel(Modifier):

    def __init__(self, fileref):
        Modifier.__init__(self, fileref)
        self.type = "channel"

    def __repr__(self):
        return ("<Channel %s %s>" % (self.id, self.type))


class Alias(Channel):

    def __init__(self, fileref):
        Channel.__init__(self, fileref)
        self.alias = None
        self.parent = None
        self.type = "alias"
        self.value = 0.0

    def __repr__(self):
        return ("<Alias %s\n  %s>" % (self.id, self.alias))

    def parse(self, struct):
        Channel.parse(self, struct)
        channel = struct["channel"]
        #self.parent = self.getAsset(struct["parent"])
        self.alias = self.getAsset(channel["target_channel"])

    def update(self, struct):
        if self.alias:
            self.alias.update(struct)
            if hasattr(self.alias, "value"):
                self.value = self.alias.value

    def build(self, context, inst):
        if self.alias:
            self.alias.build(context)

#-------------------------------------------------------------
#   Skin Binding
#-------------------------------------------------------------

class SkinBinding(Modifier):

    def __init__(self, fileref):
        Modifier.__init__(self, fileref)
        self.parent = None
        self.skin = None
        self.type = "skin_binding"

    def __repr__(self):
        return ("<SkinBinding %s>" % (self.id))


    def parse(self, struct):
        from .geometry import Geometry
        from .figure import Figure
        Modifier.parse(self, struct)
        self.skin = struct["skin"]
        self.parent = self.getAsset(struct["parent"])
        if not (isinstance(self.parent, Geometry) or
                isinstance(self.parent, Figure)):
            msg = "Parent of %s\nshould be a geometry or a figure but is\n%s" % (self, self.parent)
            if theSettings.verbosity > 1:
                print(msg)
            if theSettings.verbosity > 2:
                reportError(msg)


    def getGeoRig(self, inst):
        from .geometry import GeoNode
        from .figure import FigureInstance
        if isinstance(inst, FigureInstance):
            rig = inst.rna
            if not self.skin["geometry"]:
                return None,rig,None
            geo = self.getAsset(self.skin["geometry"])
            if geo:
                geonode = geo.getNode(0)
            else:
                geonode = None
            if geonode:
                ob = geonode.rna
            else:
                ob = None
            return ob, rig, geonode
        elif isinstance(inst, GeoNode):
            ob = inst.rna
            rig = ob.parent
            return ob, rig, inst
        else:
            msg = ("SKIN: Expected geonode but got:\n  %s" % inst)
            if theSettings.verbosity > 1:
                print(msg)
            if theSettings.verbosity > 2:
                reportError(msg)
            else:
                return None,None,None


    def build(self, context, inst):
        ob,rig,geonode = self.getGeoRig(inst)
        if ob is None or rig is None:
            return
        mod = ob.modifiers.new(self.name, 'ARMATURE')
        mod.object = rig
        mod.use_deform_preserve_volume = True
        activateObject(context, ob)
        for n in range(len(ob.modifiers)-1):
            bpy.ops.object.modifier_move_up(modifier=mod.name)
        ob.lock_location = (True,True,True)
        ob.lock_rotation = (True,True,True)
        ob.lock_scale = (True,True,True)
        self.addVertexGroups(ob, geonode, rig)


    def addVertexGroups(self, ob, geonode, rig):
        bones = geonode.figure.bones
        for joint in self.skin["joints"]:
            bname = joint["id"]
            if bname in bones.keys():
                vgname = bones[bname]
            else:
                vgname = bname

            weights = None
            if "node_weights" in joint.keys():
                weights = joint["node_weights"]
            elif "local_weights" in joint.keys():
                if bname in rig.data.bones.keys():
                    calc_weights = self.calcLocalWeights(bname, joint, rig)
                    weights = {"values": calc_weights}
                else:
                    print("Local weights missing bone:", bname)
                    for comp in ["x", "y", "z"]:
                        if comp in joint["local_weights"].keys():
                            weights = joint["local_weights"][comp]
                            break
            elif "scale_weights" in joint.keys():
                weights = joint["scale_weights"]
            else:
                if theSettings.verbosity > 1:
                    print("No weights for %s in %s" % (bname, ob.name))
                continue

            buildVertexGroup(ob, vgname, weights)


    def calcLocalWeights(self, bname, joint, rig):
        local_weights = joint["local_weights"]
        bone = rig.data.bones[bname]
        head = bone.head_local
        tail = bone.tail_local
        # find longitudinal axis of the bone and take the other two into consideration
        consider = []
        x_delta = abs(head[0] - tail[0])
        y_delta = abs(head[1] - tail[1])
        z_delta = abs(head[2] - tail[2])
        max_delta = max(x_delta, y_delta, z_delta)
        if x_delta < max_delta:
            consider.append("x")
        if y_delta < max_delta:
            consider.append("z")
        if z_delta < max_delta:
            consider.append("y")

        # create deques sorted in descending order
        weights = [collections.deque(local_weights[letter]["values"]) for letter in consider if
                   letter in local_weights]
        for w in weights:
            w.reverse()
        target = []
        calc_weights = []
        if len(weights) == 1:
            calc_weights = weights[0]
        elif len(weights) > 1:
            self.mergeWeights(weights[0], weights[1], target)
            calc_weights = target
        if len(weights) > 2:
            # this happens mostly with zero length bones
            calc_weights = []
            self.mergeWeights(target, weights[2], calc_weights)
        return calc_weights


    def mergeWeights(self, first, second, target):
        # merge the two local_weight groups and calculate arithmetic mean for vertices that are present in both groups
        while len(first) > 0 and len(second) > 0:
            a = first.pop()
            b = second.pop()
            if a[0] == b[0]:
                target.append([a[0], (a[1] + b[1]) / 2.0])
            elif a[0] < b[0]:
                target.append(a)
                second.append(b)
            else:
                target.append(b)
                first.append(a)
        while len(first) > 0:
            a = first.pop()
            target.append(a)
        while len(second) > 0:
            b = second.pop()
            target.append(b)


def buildVertexGroup(ob, vgname, weights, default=None):
    if weights and weights["values"]:
        if vgname in ob.vertex_groups.keys():
            print("Duplicate vertex group:\n  %s %s" % (ob.name, vgname))
            vgrp = ob.vertex_groups[vgname]
        else:
            vgrp = ob.vertex_groups.new(name=vgname)
        if default is None:
            for vn,w in weights["values"]:
                vgrp.add([vn], w, 'REPLACE')
        else:
            for vn in weights["values"]:
                vgrp.add([vn], default, 'REPLACE')


class LegacySkinBinding(SkinBinding):

    def __repr__(self):
        return ("<LegacySkinBinding %s>" % (self.id))

    def parse(self, struct):
        struct["skin"] = struct["legacy_skin"]
        SkinBinding.parse(self, struct)

#-------------------------------------------------------------
#   Formula
#-------------------------------------------------------------

class FormulaAsset(Formula, Modifier):

    def __init__(self, fileref):
        Modifier.__init__(self, fileref)
        Formula.__init__(self)
        self.value = 0
        self.min = None
        self.max = None
        self.group = ""


    def __repr__(self):
        return ("<Formula %s %f>" % (self.id, self.value))


    def parse(self, struct):
        Modifier.parse(self, struct)
        if not theSettings.useMorph:
            return
        if "channel" in struct.keys():
            channel = struct["channel"]
            if "value" in channel.keys():
                self.value = channel["value"]
            if "min" in channel.keys():
                self.min = channel["min"]
            if "max" in channel.keys():
                self.max = channel["max"]
        if "group" in struct.keys():
            words = struct["group"].split("/")
            if (len(words) > 2 and
                words[0] == "" and
                words[1] == "Pose Controls"):
                self.group = words[2]
        Formula.parse(self, struct)


    def update(self, struct):
        Modifier.update(self, struct)
        if ("channel" in struct.keys() and
            "current_value" in struct["channel"].keys()):
            self.value = struct["channel"]["current_value"]


    def build(self, context, inst):
        if not theSettings.useMorph:
            return
        Formula.prebuild(self, context, inst)
        if self.group in ["Feet", "Legs", "Arms", "Head", "Torso", "Hip"]:
            if theSettings.makeDrivers in ['PEOPLE', 'ALL']:
                Formula.build(self, context, inst)
        else:
            if theSettings.makeDrivers in ['PROPS', 'ALL']:
                Formula.build(self, context, inst)


    def postbuild(self, context, inst):
        if not theSettings.useMorph:
            return
        Formula.postbuild(self, context, inst)

#-------------------------------------------------------------
#   Morph
#-------------------------------------------------------------

class Morph(FormulaAsset):

    def __init__(self, fileref):
        FormulaAsset.__init__(self, fileref)
        self.type = "morph"
        self.vertex_count = 0


    def __repr__(self):
        return ("<Morph %s %f>" % (self.id, self.value))


    def parse(self, struct):
        FormulaAsset.parse(self, struct)
        if not theSettings.useMorph:
            return
        self.parent = struct["parent"]
        self.deltas = struct["morph"]["deltas"]["values"]
        self.vertex_count = struct["morph"]["vertex_count"]


    def update(self, struct):
        from .geometry import GeoNode, Geometry
        from .figure import Figure, FigureInstance
        FormulaAsset.update(self, struct)
        if not theSettings.useMorph:
            return

        parent = self.getAsset(self.parent)
        if "parent" not in struct.keys():
            return

        if isinstance(parent, Geometry):
            ref = instRef(struct["parent"])
            if ref in parent.nodes:
                geonode = parent.nodes[ref]
            else:
                if theSettings.verbosity > 3:
                    print("Missing geonode %s in\n %s" %(ref, parent))
                return
        elif isinstance(parent, GeoNode):
            geonode = parent
        elif isinstance(parent, Figure) and parent.instances:
            ref = list(parent.instances.keys())[0]
            inst = parent.getInstance(self.caller, ref)
            geonode = inst.geometries[0]
        elif isinstance(parent, FigureInstance):
            geonode = parent.geometries[0]
        else:
            msg = ("Strange morph parent.\n  %s\n  %s" % (self, parent))
            return reportError(msg)
        geonode.morphsValues[self.name] = self.value


    def addModifier(self, inst):
        if inst:
            inst.modifiers.append(self)


    def build(self, context, inst, value=-1):
        from .geometry import GeoNode, Geometry
        from .figure import FigureInstance
        from .bone import BoneInstance

        if not theSettings.useMorph:
            return self
        Formula.prebuild(self, context, inst)
        Modifier.build(self, context)

        if isinstance(inst, FigureInstance):
            geonodes = inst.geometries
        elif isinstance(inst, GeoNode):
            geonodes = [inst]
        elif isinstance(inst, BoneInstance):
            geonodes = inst.figure.geometries
        else:
            asset = self.getAsset(self.parent)
            print("BMO", inst)
            print("  ", asset)
            inst = None
            if asset:
                geonodes = list(asset.nodes.values())
                if len(geonodes) > 0:
                    inst = geonodes[0]

        if inst is None:
            msg = ("Morph not found:\n  %s\n  %s\n  %s" % (self.id, self.parent, asset))
            if theSettings.verbosity > 2:
                reportError(msg)
            elif theSettings.verbosity > 1:
                print(msg)
            return None
        cscale = inst.getCharacterScale()

        for geonode in geonodes:
            ob = geonode.rna
            if value >= 0:
                self.value = value
                if self not in geonode.modifiers:
                    geonode.modifiers.append(self)
                geonode.morphsValues[self.name] = value
            elif self.name in geonode.morphsValues.keys():
                self.value = geonode.morphsValues[self.name]
            else:
                if theSettings.verbosity > 3:
                    print("MMMO", self.name)
                    print("  ", geonode)
                    print("  ", geonode.morphsValues.keys())
                self.value = 0.0

            if ob is None:
                continue
            elif theSettings.applyMorphs:
                self.addMorphToVerts(ob.data, cscale)
            elif self.value > 0.0:
                self.buildMorph(ob, cscale)
        return self


    def addMorphToVerts(self, me, cscale):
        if self.value == 0.0:
            return

        scale = self.value * cscale * theSettings.scale
        for delta in self.deltas:
            vn = delta[0]
            me.vertices[vn].co += scale * d2bu(delta[1:])


    def buildMorph(self, ob, cscale, useSoftLimits=False):
        if not ob.data.shape_keys:
            basic = ob.shape_key_add(name="Basic")
        else:
            basic = ob.data.shape_keys.key_blocks[0]
        sname = getName(self.id)
        if sname in ob.data.shape_keys.key_blocks.keys():
            skey = ob.data.shape_keys.key_blocks[sname]
            ob.shape_key_remove(skey)
        skey = ob.shape_key_add(name=sname)
        if useSoftLimits:
            skey.slider_min = self.min if self.min is not None and theSettings.useDazPropLimits else theSettings.propMin
            skey.slider_max = self.max if self.max is not None and theSettings.useDazPropLimits else theSettings.propMax
        skey.value = self.value
        self.rna = (skey, ob, sname)
        self.buildShapeKey(ob, skey, cscale)


    def buildShapeKey(self, ob, skey, cscale):
        for v in ob.data.vertices:
            skey.data[v.index].co = v.co

        scale = cscale * theSettings.scale
        if theSettings.zup:
            for delta in self.deltas:
                vn = delta[0]
                skey.data[vn].co += scale * d2b90u(delta[1:])
        else:
            for delta in self.deltas:
                vn = delta[1]
                skey.data[vn].co += scale * d2b00u(delta[1:])


    def rebuild(self, geonode, value):
        ob = geonode.rna
        cscale = geonode.getCharacterScale()
        self.value = value
        if (ob.data.shape_keys and
            self.name in ob.data.shape_keys.key_blocks.keys()):
            skey = ob.data.shape_keys.key_blocks[self.name]
            skey.value = value
            self.buildShapeKey(ob, skey, cscale)
        else:
            if theSettings.applyMorphs:
                self.addMorphToVerts(ob.data, cscale)
            elif ob:
                if self.value > 0.0:
                    self.buildMorph(ob, cscale)
            #raise DazError("No such shapekey %s in %s" % (skey, ob))
