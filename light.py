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
from .node import Node
from .utils import *
from .cycles import Material, CyclesMaterial, CyclesTree
from .material import WHITE, BLACK
from .settings import theSettings

#-------------------------------------------------------------
#   Light base class
#-------------------------------------------------------------

class Light(Node):

    def __init__(self, fileref):
        Node.__init__(self, fileref)
        self.type = None
        self.info = {}
        self.presentation = {}
        self.channels = {}
        self.data = None
        self.material = None
        self.twosided = False


    def __repr__(self):
        return ("<Light %s %s>" % (self.id, self.rna))


    def parse(self, struct):
        Node.parse(self, struct)
        if "spot" in struct.keys():
            self.type = 'SPOT'
            self.info = struct["spot"]
        elif "point" in struct.keys():
            self.type = 'POINT'
            self.info = struct["point"]
        elif "directional" in struct.keys():
            self.type = 'DIRECTIONAL'
            self.info = struct["directional"]
        else:
            self.presentation = struct["presentation"]
            print("Strange lamp", self)
        if "extra" in struct.keys():
            for estruct in struct["extra"]:
                if estruct["type"] == "studio_node_channels":
                    self.channels = estruct["channels"]

    def build(self, context, inst=None):
        if theSettings.renderMethod in ['BLENDER_RENDER', 'BLENDER_GAME']:
            self.material = InternalLightMaterial(self)
        else:
            self.material = CyclesLightMaterial(self)
        self.material.build(context)
        Node.build(self, context, inst)


    def postTransform(self):
        if theSettings.zup:
            ob = self.rna
            ob.rotation_euler[0] += math.pi/2


    def postbuild(self, context, inst):
        Node.postbuild(self, context, inst)
        if self.twosided:
            if inst.rna:
                ob = inst.rna
                activateObject(context, ob)
                bpy.ops.object.duplicate_move()
                nob = getActiveObject(context)
                nob.data = ob.data
                nob.scale = -ob.scale

#-------------------------------------------------------------
#   LightMaterial
#-------------------------------------------------------------

class LightMaterial:
    def __init__(self, light):
        self.light = light
        self.fluxFactor = 1
        self.channels = {}
        for cstruct in light.channels:
            channel = cstruct["channel"]
            if "id" in channel.keys():
                key = channel["id"]
                self.channels[key] = channel


    def build(self, context):
        light = self.light
        lgeo = self.getValue(["Light Geometry"], -1)
        usePhoto = self.getValue(["Photometric Mode"], False)
        light.twosided = self.getValue(["Two Sided"], False)

        height = self.getValue(["Height"], 0) * theSettings.scale
        width = self.getValue(["Width"], 0) * theSettings.scale

        # [ "Point", "Rectangle", "Disc", "Sphere", "Cylinder" ]
        if bpy.app.version < (2,80,0):
            bpydatalamps = bpy.data.lamps
        else:
            bpydatalamps = bpy.data.lights
        if lgeo == 1:
            lamp = bpydatalamps.new(light.name, "AREA")
            lamp.shape = 'RECTANGLE'
            lamp.size = width
            lamp.size_y = height
        elif lgeo > 1:
            lamp = bpydatalamps.new(light.name, "POINT")
            lamp.shadow_soft_size = height/2
        elif light.type == 'SPOT':
            lamp = bpydatalamps.new(light.name, "SPOT")
            lamp.shadow_soft_size = height/2
        elif light.type == 'POINT':
            lamp = bpydatalamps.new(light.name, "POINT")
            lamp.shadow_soft_size = 0
            self.fluxFactor = 5
        elif light.type == 'DIRECTIONAL':
            lamp = bpydatalamps.new(light.name, "SUN")
            lamp.shadow_soft_size = height/2
        elif light.type == 'light':
            lamp = bpydatalamps.new(light.name, "AREA")
        else:
            msg = ("Unknown light type: %s" % light.type)
            if theSettings.verbosity > 2:
                raise DazError(msg)
            else:
                print(msg)
                lamp = bpydatalamps.new(light.name, "SPOT")
                lamp.shadow_soft_size = height/2

        self.setLampProps(lamp, light.info, context)
        self.setChannels(lamp)

        self.rna = light.data = lamp


    def setLampProps(self, lamp, props, context):
        if context.scene.render.engine not in ["BLENDER_RENDER", "BLENDER_GAME"]:
            return
        for key,value in props.items():
            if key == "intensity":
                lamp.energy = value
            elif key == "shadow_type":
                if bpy.app.version < (2,80,0):
                    if value == "none":
                        lamp.shadow_method = 'NOSHADOW'
                    else:
                        lamp.shadow_method = 'RAY_SHADOW'
                else:
                    if value == "none":
                        lamp.cycles.cast_shadow = False
                    else:
                        lamp.cycles.case_shadow = True
            elif key == "shadow_softness":
                lamp.shadow_buffer_soft = value
            elif key == "shadow_bias":
                lamp.shadow_buffer_bias = value
            elif key == "falloff_angle":
                if hasattr(lamp, "spot_size"):
                    lamp.spot_size = value*D
            elif key == "falloff_exponent":
                if hasattr(lamp, "distance"):
                    lamp.distance = value
            else:
                print("Unknown lamp prop", key)


    def setChannels(self, lamp):
        if bpy.app.version < (2,80,0):
            if self.getValue(["Cast Shadows"], 0):
                lamp.shadow_method = 'RAY_SHADOW'
            else:
                lamp.shadow_method = 'NOSHADOW'
            value = self.getValue(["Shadow Type"], 0)
            stypes = ['NOSHADOW', 'BUFFER_SHADOW', 'RAY_SHADOW']
            lamp.shadow_method = stypes[value]
        else:
            if self.getValue(["Cast Shadows"], 0):
                lamp.cycles.cast_shadow = True
            else:
                lamp.cycles.cast_shadow = False

        if bpy.app.version < (2,80,0):
            value = self.getValue(["Illumination"], 3)
            # [ "Off", "Diffuse Only", "Specular Only", "On" ]
            lamp.use_diffuse = (value in [1,3])
            lamp.use_specular = (value in [2,3])

        lamp.color = self.getValue(["Color"], WHITE)
        flux = self.getValue(["Flux"], 1500)
        lamp.energy = flux / 15000 * self.fluxFactor
        lamp.shadow_color = self.getValue(["Shadow Color"], BLACK)
        if hasattr(lamp, "shadow_buffer_soft"):
            lamp.shadow_buffer_soft = self.getValue(["Shadow Softness"], False)
        if hasattr(lamp, "shadow_buffer_bias"):
            bias = self.getValue(["Shadow Bias"], None)
            if bias:
                lamp.shadow_buffer_bias = bias
        if hasattr(lamp, "falloff_type"):
            value = self.getValue(["Decay"], 2)
            dtypes = ['CONSTANT', 'INVERSE_LINEAR', 'INVERSE_SQUARE']
            lamp.falloff_type = dtypes[value]

#-------------------------------------------------------------
#   InternalLightMaterial
#-------------------------------------------------------------

class InternalLightMaterial(Material, LightMaterial):
    def __init__(self, light):
        Material.__init__(self, light.fileref)
        LightMaterial.__init__(self, light)


    def build(self, context):
        LightMaterial.build(self, context)

#-------------------------------------------------------------
#   Cycles Light
#-------------------------------------------------------------

class CyclesLightMaterial(CyclesMaterial, LightMaterial):

    def __init__(self, light):
        CyclesMaterial.__init__(self, light.fileref)
        LightMaterial.__init__(self, light)

    def __repr__(self):
        return ("<CLight %s %s>" % (self.light.rna, self.rna))

    def build(self, context):
        LightMaterial.build(self, context)
        self.tree = LightTree(self)
        self.tree.build(context)


class LightTree(CyclesTree):

    def build(self, context):
        self.makeTree()
        color = self.getValue(["Color"], WHITE)
        flux = self.getValue(["Flux"], 1500) * self.material.fluxFactor

        emit = self.addNode(1, "ShaderNodeEmission")
        emit.inputs["Color"].default_value[0:3] = color
        emit.inputs["Strength"].default_value = flux / 15000
        if bpy.app.version < (2,80,0):
            output = self.addNode(2, "ShaderNodeOutputLamp")
        else:
            output = self.addNode(2, "ShaderNodeOutputLight")
        self.links.new(emit.outputs[0], output.inputs["Surface"])


    def addTexco(self, slot):
        return


def getValue(channel, default):
    if "current_value" in channel.keys():
        return channel["current_value"]
    elif "value" in channel.keys():
        return channel["value"]
    else:
        return default



