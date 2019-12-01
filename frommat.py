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
from .material import Material, WHITE, BLACK
from .utils import *
from .settings import theSettings
from .error import *

#-------------------------------------------------------------
#   From internal
#-------------------------------------------------------------

class FromInternal:

    def fromMaterial(self, mat, ob, struct):
        from .asset import normalizeRef

        materialAttrs = [
            ("diffuse", "diffuse_color", "use_map_color_diffuse", 1),
            ("specular_strength", "specular_intensity", "use_map_specular", 1),
            ("glossiness", "specular_hardness", "use_map_hardness", 1.0/512),
            ("transparency", "alpha", "use_map_alpha", 1),
            ("bump", None, "use_map_normal", 1),
            ("normal", None, "use_map_normal", 1),
        ]
        scale = ob.DazScale
        channels = {}
        for daz,key,use,fac in materialAttrs:
            if key:
                attr = getattr(mat, key)
                if fac == 1:
                    value = attr
                else:
                    value = fac*attr
                if daz not in struct.keys():
                    channel = channels[daz] = {"id" : daz}
                    struct[daz] = {"channel" : channel}
                channels[daz]["current_value"] = value

        stencil = None
        for mtex in mat.texture_slots:
            if mtex is None:
                continue
            tex = mtex.texture
            for daz,key,use,fac in materialAttrs:
                channel = None
                if getattr(mtex,use):
                    if ((daz == "bump" and tex.use_normal_map) or
                        (daz == "normal" and not tex.use_normal_map)):
                        continue
                    if (daz == "diffuse" and
                        mtex.use_map_alpha and
                        "transparency" in struct.keys()):
                        del struct["transparency"]
                    if daz not in struct.keys():
                        channel = channels[daz] = {"id" : daz}
                        struct[daz] = {"channel" : channel}
                    channel = channels[daz]
                    break
            if channel:
                self.addImage(daz, tex, channel, stencil)
            if mtex.use_stencil:
                stencil = mtex.texture
            else:
                stencil = None


    def addImage(self, daz, tex, channel, stencil):
        if tex.type == 'IMAGE':
            img = tex.image
            color = (tex.factor_red, tex.factor_green, tex.factor_blue)
        elif tex.type == 'BLEND':
            img = None
            color = list(tex.color_ramp.elements[0].color)[0:3]
        else:
            img = None
            color = (1,1,1)
            print("Unknown texture type: %s" % tex.type)

        if "literal_maps" in channel.keys():
            image = channel["literal_maps"]
        elif "literal_image" not in channel.keys():
            channel["literal_image"] = img
            channel["current_value"] = color
            image = None
        else:
            map = {
                "literal_image" : channel["literal_image"],
                "current_value" : color
                }
            del channel["literal_image"]
            image = channel["literal_maps"] = {
                "id" : daz + "_" + tex.name,
                "map" : [map]
            }

        if image:
            map = {}
            if img:
                map["literal_image"] = img
            map["color"] = color
            if stencil:
                mask = {"literal_image" : stencil.image}
                map["mask"] = mask
            image["map"].append(map)

#-------------------------------------------------------------
#   From cycles
#-------------------------------------------------------------

class FromCycles:

    def fromMaterial(self, mat, ob, struct):
        from .asset import normalizeRef

        scale = ob.DazScale
        self.material.shader == 'IRAY'
        for node in mat.node_tree.nodes.values():
            if node.type == 'BSDF_DIFFUSE':
                self.addColorChannel("Diffuse Color", "Color", node, struct)
                # self.makeChannel("Diffuse Strength", struct, 1.0)
            elif node.type == 'BSDF_GLOSSY':
                self.addColorChannel("Specular Color", "Color", node, struct)
                # self.makeChannel("Specular Strength", struct, 1.0)
                self.addScalarChannel("Glossy Roughness", "Roughness", node, struct)
            elif node.type == 'BSDF_TRANSPARENT':
                self.addTransparent("Cutout Opacity", node, struct)
            elif node.type == 'SUBSURFACE_SCATTERING':
                self.addColorChannel("SSS Color", "Color", node, struct)
                self.addScalarChannel("SSS Scale", "Radius", node, struct, 1/scale)
                self.addScalarChannel("SSS Radius", "Scale", node, struct, 1/scale)
            elif node.type == 'BUMP':
                channel = self.addScalarChannel("Bump", "Height", node, struct)
                channel["current_value"] = node.inputs["Strength"].default_value
                dist = node.inputs["Distance"].default_value/scale
                self.makeChannel("Bump Minimum", struct, -dist/2)
                self.makeChannel("Bump Maximum", struct, dist/2)
            elif node.type == 'NORMAL_MAP':
                self.addColorChannel("Normal Map", "Color", node, struct)
            elif node.type == 'BSDF_REFRACTION':
                self.addColorChannel("Refraction Color", "Color", node, struct)
                self.addScalarChannel("Refraction Roughness", "Roughness", node, struct)
                self.addScalarChannel("Refraction Index", "IOR", node, struct)
            elif node.type == 'BSDF_PRINCIPLED':
                self.addColorChannel("Diffuse Color", "Base Color", node, struct)
                self.addScalarChannel("SSS Amount", "Subsurface", node, struct)
                self.addColorChannel("SSS Color", "Subsurface Color", node, struct)
                self.addColorChannel("SSS Radius", "Subsurface Radius", node, struct, 1/scale)
                self.addScalarChannel("Metallic Weight", "Metallic", node, struct)
                self.addScalarChannel("Specular Strength", "Specular", node, struct)
                self.addScalarChannel("Glossy Roughness", "Roughness", node, struct)
                self.addScalarChannel("Glossy Anisotropy", "Anisotropic", node, struct)
                self.addScalarChannel("Glossy Anisotropy Rotations", "Anisotropic Rotation", node, struct)
                self.addScalarChannel("Backscattering Weight", "Sheen", node, struct)
                self.addScalarChannel("Top Coat Weight", "Clearcoat", node, struct)
                self.addScalarChannel("Top Coat Roughness", "Clearcoat Roughness", node, struct)
                self.addScalarChannel("Refraction Index", "IOR", node, struct)
                self.addScalarChannel("Refraction Strength", "Transmission", node, struct)

        #print("\n", mat.name)
        #print(struct)
        return struct


    def makeChannel(self, name, struct, value=None):
        channel = {"id" : name}
        if value is not None:
            channel["current_value"] = value
        struct[name] = {"channel" : channel}
        return channel


    def addColorChannel(self, name, slot, bsdf, struct, factor=1.0):
        channel = self.makeChannel(name, struct)
        color = list(bsdf.inputs[slot].default_value)[0:3]
        channel["current_value"] = factor*Vector(color)
        node = self.getLinkFrom(bsdf, slot)
        if node:
            if node.type == 'TEX_IMAGE':
                setLiteralImage(channel, node)
                channel["current_value"] = WHITE
            elif node.type == 'MIX_RGB':
                img1 = self.getLinkFrom(node, "Color1")
                img2 = self.getLinkFrom(node, "Color2")
                if img1:
                    color2 = list(node.inputs[2].default_value)[0:3]
                    channel["current_value"] = factor*Vector(color2)
                    setLiteralImage(channel, img1)
                elif img2:
                    color1 = list(node.inputs[1].default_value)[0:3]
                    channel["current_value"] = factor*Vector(color1)
                    setLiteralImage(channel, img2)
        return channel


    def addScalarChannel(self, name, slot, bsdf, struct, factor=1.0):
        channel = self.makeChannel(name, struct)
        channel["current_value"] = factor * averageColor(bsdf.inputs[slot].default_value)
        node = self.getLinkFrom(bsdf, slot)
        if node:
            if node.type == 'TEX_IMAGE':
                setLiteralImage(channel, node)
                channel["current_value"] = factor
            elif node.type == 'MIX_RGB':
                img1 = self.getLinkFrom(node, "Color1")
                img2 = self.getLinkFrom(node, "Color2")
                if img1:
                    color2 = list(node.inputs[2].default_value)[0:3]
                    channel["current_value"] = factor*averageColor(color2)
                    setLiteralImage(channel, img1)
                elif img2:
                    color1 = list(node.inputs[1].default_value)[0:3]
                    channel["current_value"] = factor*averageColor(color1)
                    setLiteralImage(channel, img2)
        return channel


    def addTransparent(self, name, bsdf, struct):
        channel = self.makeChannel(name, struct)

        mix = self.getLinkTo(bsdf, "BSDF")
        if mix is None:
            del struct[name]
            return

        hsv = self.getLinkFrom(mix, "Fac")
        if hsv is None:
            try:
                channel["current_value"] = mix.inputs["Fac"].default_value
            except KeyError:
                return
            channel["image"] = None
            return
        elif hsv.type == 'TEX_IMAGE':
            img = hsv
            node = self.getLinkTo(img, "Color")
            if node != mix:
                del struct[name]
                return
        else:
            return

        channel["current_value"] = 1
        setLiteralImage(channel, img)


def setLiteralImage(channel, img):
    if hasattr(img, "image"):
        channel["literal_image"] = img.image
    else:
        print("Missing image:", img)
        channel["image"] = None

# ---------------------------------------------------------------------
#   Toggle render engine
# ---------------------------------------------------------------------

def updateForEngine(context):
    if bpy.app.version < (2,80,0):
        updateCyclesInternal(context)
    else:
        value = (context.scene.render.engine != 'CYCLES')
        for ob in getSceneObjects(context):
            if ob.type == 'MESH':
                for mod in ob.modifiers:
                    if mod.type == 'MASK' and mod.name == "HiddenEevee":
                        setattr(mod, "show_viewport", value)
                        setattr(mod, "show_render", value)


def updateCyclesInternal(context):
    from .material import clearMaterials
    from .internal import InternalMaterial
    from .cycles import CyclesMaterial
    from .geometry import Uvset

    scn = context.scene
    useNodes = (scn.render.engine not in ['BLENDER_RENDER', 'BLENDER_GAME'])
    theSettings.forEngine(scn)
    clearMaterials()
    for ob in getSceneObjects(context):
        if ob.type == 'MESH':
            for n,mat in enumerate(ob.data.materials):
                if mat.DazRenderEngine == 'NONE':
                    if mat.use_nodes:
                        mat.DazRenderEngine = 'CYCLES'
                    else:
                        mat.DazRenderEngine = 'BLENDER_RENDER'
                if (mat.DazRenderEngine == 'BLENDER_RENDER' and useNodes):
                        asset1 = InternalMaterial("")
                        asset2 = CyclesMaterial("")
                elif (mat.DazRenderEngine != 'BLENDER_RENDER' and not useNodes):
                        asset1 = CyclesMaterial("")
                        asset2 = InternalMaterial("")
                else:
                    continue

                struct = asset1.fromMaterial(mat, ob)
                asset2.parse(struct)
                if getUvTextures(ob.data):
                    asset2.uv_set = Uvset("")
                    asset2.uv_set.name = getUvTextures(ob.data)[0].name
                asset2.rna = mat
                color = tuple(mat.diffuse_color)
                asset2.build(context)
                mat.diffuse_color = color
                mat.DazRenderEngine = 'BOTH'

    for ob in getSceneObjects(context):
        if ob.type == 'MESH':
            for mat in ob.data.materials:
                mat.use_nodes = useNodes

    print("Materials updated for %s" % scn.render.engine)


class DAZ_OT_UpdateForEngine(bpy.types.Operator):
    bl_idname = "daz.update_for_engine"
    bl_label = "Update For Engine"
    bl_description = "Update all materials for the current render engine"
    bl_options = {'UNDO'}

    def execute(self, context):
        try:
            updateForEngine(context)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_UpdateForEngine,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
