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
from .asset import Asset
from .material import Material, WHITE
from .cycles import CyclesMaterial, CyclesTree
from .settings import theSettings
from .utils import *

#-------------------------------------------------------------
#   Render Options
#-------------------------------------------------------------

class RenderOptions(Asset):
    def __init__(self, fileref):
        Asset.__init__(self, fileref)
        self.channels = {}
        self.world = None


    def __repr__(self):
        return ("<RenderOptions %s>" % (self.fileref))


    def parse(self, struct):
        for key,clist in struct.items():
            if key == "channels":
                for channel in clist:
                    self.setChannel(channel)
            elif key == "children":
                for child in clist:
                    if "channels" in child.keys():
                        for channel in child["channels"]:
                            self.setChannel(channel)


    def setChannel(self, cstruct):
        channel = cstruct["channel"]
        if ("visible" not in channel.keys() or
            channel["visible"]):
            self.channels[channel["id"]] = channel


    def build(self, context):
        if theSettings.useEnvironment:
            self.world = WorldMaterial(self.fileref)
            self.world.build(context, self.channels)

#-------------------------------------------------------------
#   World Material
#-------------------------------------------------------------

class WorldMaterial(CyclesMaterial):

    def __init__(self, fileref):
        CyclesMaterial.__init__(self, fileref)
        self.name = os.path.splitext(os.path.basename(fileref))[0] + " World"


    def build(self, context, channels):
        self.refractive = False
        Material.build(self, context)
        self.channels = channels
        self.tree = WorldTree(self)

        if not self.getValue(["Draw Dome"], False):
            print("Don't draw environment. Draw Dome turned off")
            return

        mode = self.getValue(["Environment Mode"], 0)
        if mode not in [0,1]:
            print("Dont draw environment. Environment mode == %d" % mode)
            return
        channel = self.getChannel(["Environment Map"])
        if not (channel and self.getImageFile(channel)):
            print("Don't draw environment. Image file not found")
            return

        world = self.rna = bpy.data.worlds.new(self.name)
        world.use_nodes = True
        self.tree.build(context)
        context.scene.world = world

#-------------------------------------------------------------
#   World Tree
#-------------------------------------------------------------

class WorldTree(CyclesTree):

    def __init__(self, wmat):
        CyclesTree.__init__(self, wmat)
        self.type == "WORLD"


    def build(self, context):
        from mathutils import Euler, Matrix

        self.makeTree(slot="Generated")

        rot = self.getValue(["Dome Rotation"], 0)
        orx = self.getValue(["Dome Orientation X"], 0)
        ory = self.getValue(["Dome Orientation Y"], 0)
        orz = self.getValue(["Dome Orientation Z"], 0)

        if rot != 0 or orx != 0 or ory != 0 or orz != 0:
            mat1 = Euler((0,0,-rot*D)).to_matrix()
            mat2 = Euler((0,-orz*D,0)).to_matrix()
            mat3 = Euler((orx*D,0,0)).to_matrix()
            mat4 = Euler((0,0,ory*D)).to_matrix()
            mat = Mult4(mat1, mat2, mat3, mat4)
            self.addMapping(mat.to_euler())

        channel = self.material.getChannel(["Environment Map"])
        value = self.material.getChannelValue(channel, 1)
        tex = self.addTexEnvNode(channel, "NONE")
        self.links.new(self.texco, tex.inputs["Vector"])

        bg = self.addNode(5, "ShaderNodeBackground")
        strength = self.getValue(["Environment Intensity"], 1)
        bg.inputs["Strength"].default_value = strength * value
        self.links.new(tex.outputs[0], bg.inputs["Color"])

        output = self.addNode(5, "ShaderNodeOutputWorld")
        self.links.new(bg.outputs[0], output.inputs["Surface"])


    def addMapping(self, rot):
        mapping = self.addNode(2, "ShaderNodeMapping")
        mapping.vector_type = 'TEXTURE'
        mapping.rotation = rot
        self.links.new(self.texco, mapping.inputs["Vector"])
        self.texco = mapping.outputs["Vector"]


    def addTexEnvNode(self, channel, colorSpace):
        assets,maps = self.material.getTextures(channel)
        asset = assets[0]
        img = asset.images[colorSpace]
        if img is None:
            img = asset.buildCycles(colorSpace)

        tex = self.addNode(4, "ShaderNodeTexEnvironment")
        self.setColorSpace(tex, colorSpace)
        if img:
            tex.image = img
            tex.name = img.name
        return tex


#-------------------------------------------------------------
#
#-------------------------------------------------------------

def parseRenderOptions(struct, fileref):
    if theSettings.renderMethod in ['BLENDER_RENDER', 'BLENDER_GAME']:
        return None
    else:
        if "render_options" in struct.keys():
            ostruct = struct["render_options"]
            if "render_elements" in ostruct.keys():
                asset = RenderOptions(fileref)
                for estruct in ostruct["render_elements"]:
                    asset.parse(estruct)
                return asset
    return None
