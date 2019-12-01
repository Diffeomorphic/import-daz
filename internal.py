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
from mathutils import Vector
from .material import Material, WHITE, BLACK, setImageColorSpace
from .frommat import FromInternal
from .settings import theSettings

class InternalMaterial(Material, FromInternal):

    def __repr__(self):
        return ("<Internal %s r: %s>" % (self.id, self.rna))


    def fromMaterial(self, mat, ob):
        struct = Material.fromMaterial(self, mat, ob)
        FromInternal.fromMaterial(self, mat, ob, struct)
        return struct


    def build(self, context):
        from .guess import castsShadow
        if self.ignore:
            return
        Material.build(self, context)
        scn = context.scene
        mat = self.rna
        mat.specular_intensity = 0.05
        mat.diffuse_shader = scn.DazDiffuseShader
        mat.specular_shader = scn.DazSpecularShader

        self.buildDiffuse(mat, scn)
        if self.isActive("Specular"):
            self.buildSpecular(mat)
        if theSettings.useReflection and self.isActive("Reflection"):
            self.buildReflection(mat)
        if self.sssActive():
            self.buildSSS(mat)
        if theSettings.useTranslucency and self.isActive("Translucency"):
            self.buildTranslucency(mat)
        if theSettings.useEmission and self.isActive("Emission"):
            self.buildEmission(mat)
        if self.isActive("Normal"):
            self.buildNormal(mat)
        if self.isActive("Bump"):
            self.buildBump(mat)
        if theSettings.useDisplacement and self.isActive("Displacement"):
            self.buildDisplacement(mat)
        self.buildTransparency(mat)

        if not castsShadow(mat):
            mat.use_cast_shadows = False
            mat.use_shadows = False
            mat.use_transparency = True
            mat.alpha = 0


    def buildDiffuse(self, mat, scn):
        channel = self.getChannelDiffuse()
        if channel:
            mat.diffuse_color = self.getChannelColor(channel, WHITE)
            mtexs = self.buildMtexs(channel, "sRGB", mat.diffuse_color)
            for mtex in mtexs:
                if mtex and not mtex.use_stencil:
                    mtex.use_map_color_diffuse = True
                    mtex.diffuse_color_factor = 1.0
                    if not self.hasTransparency():
                        mat.use_transparency = True
                        mat.alpha = 0
                        mat.specular_alpha = 0
                        mtex.use_map_alpha = True
                        mtex.alpha_factor = 1.0
            for shell,uv in self.shells:
                mtex = self.buildShellMTex(shell, "getChannelDiffuse", uv, "sRGB")
                if mtex:
                    mtex.use_map_color_diffuse = True

        channel = self.getChannelDiffuseStrength()
        if channel:
            mat.diffuse_intensity = self.getChannelValue(channel, 0.8)
            mtexs = self.buildMtexs(channel, "Non-Color")
            for mtex in mtexs:
                if mtex and not mtex.use_stencil:
                    mtex.use_map_diffuse = True
                    mtex.diffuse_factor = 1.0
                    mtex.use_rgb_to_intensity = True

        channel = self.getChannelDiffuseRoughness()
        mat.roughness = self.getChannelValue(channel, scn.DazDiffuseRoughness)


    def buildShellMTex(self, shell, attr, uv, colorspace):
        uvset = self.getUvSet(uv)

        channel1 = shell.getChannelCutoutOpacity()
        if channel1 and shell.hasTextures(channel1):
            channel2 = shell.getChannel(attr)
            if channel2 and shell.hasTextures(channel2):
                assets1,maps1 = shell.getTextures(channel1)
                asset1 = assets1[0]
                asset1.buildInternal()
                mtex = self.buildMtex(asset1, None)
                mtex.blend_type = 'MULTIPLY'
                mtex.use_rgb_to_intensity = True
                mtex.use_stencil = True
                mtex.uv_layer = uvset.name
                tex = mtex.texture
                if tex and tex.image:
                    setImageColorSpace(tex.image, "Non-Color")

                assets2,maps2 = shell.getTextures(channel2)
                asset2 = assets2[0]
                asset2.buildInternal()
                color = shell.getChannelColor(channel2, WHITE)
                mtex = self.buildMtex(asset2, color)
                mtex.uv_layer = uvset.name
                tex = mtex.texture
                if tex and tex.image:
                    setImageColorSpace(tex.image, colorspace)
                return mtex
        return None


    def buildSpecular(self, mat):
        channel = self.getChannelSpecularColor()
        mat.specular_color = self.getChannelColor(channel, WHITE)
        if channel:
            mtexs = self.buildMtexs(channel, "Non-Color", mat.specular_color)
            for mtex in mtexs:
                if mtex and not mtex.use_stencil:
                    mtex.use_map_color_spec = True
                    mtex.specular_color_factor = 1

        channel = self.getChannelSpecularStrength()
        mat.specular_intensity = self.getChannelValue(channel, 0)
        if channel:
            mtexs = self.buildMtexs(channel, "Non-Color")
            for mtex in mtexs:
                if mtex and not mtex.use_stencil:
                    mtex.use_map_specular = True
                    mtex.specular_factor = 1
                    mtex.use_rgb_to_intensity = True

        channel = self.getChannelIOR()
        if channel:
            mat.specular_ior = self.getChannelValue(channel, 1.0)

        channel,invert = self.getChannelGlossiness()
        value = self.getChannelValue(channel, 50/512)
        if invert:
            value = 1-value
        mat.specular_hardness = 512*value


    def buildReflection(self, mat):
        channel = self.getChannelAmbientStrength()
        mat.ambient = self.getChannelValue(channel, 1.0)

        channel = self.getChannelReflectionColor()
        mat.mirror_color = self.getChannelColor(channel, WHITE)

        channel = self.getChannelReflectionStrength()
        value = self.getChannelValue(channel, 0.0)
        if False and value > 0:
            mat.raytrace_mirror.use = True
            mat.raytrace_mirror.reflect_factor = value


    def buildSSS(self, mat):
        channel = self.getChannelSSSAmount()
        amount =  self.getChannelValue(channel, 0)
        if amount == 0:
            return
        sss = mat.subsurface_scattering
        mat.DazUseSSS = True
        sss.use = True
        sss.scale = 0.1 * theSettings.scale
        sss.color_factor = amount
        channel = self.getChannelSSSColor()
        if channel:
            sss.color = self.getChannelColor(channel, WHITE)
        channel = self.getChannelSSSScale()
        if channel:
            sss.scale = 0.1 * theSettings.scale * self.getChannelValue(channel, 1.0)
        channel = self.getChannelSSSIOR()
        if channel:
            sss.ior = self.getChannelValue(channel, 1.3)
        #channel = self.getChannelSSSRadius()
        #if channel:
        #    sss.radius = 0.1 * theSettings.scale * self.getChannelValue(channel, WHITE)


    def buildTranslucency(self, mat):
        channel = self.getChannelTranslucencyWeight()
        if channel:
            mat.translucency = self.getChannelValue(channel, 1.0)
            mat.DazUseTranslucency = True
            for mtex in self.buildMtexs(channel, "sRGB"):
                if mtex and not mtex.use_stencil:
                    mtex.use_map_translucency = True
                    mtex.translucency_factor = 1.0
                    mtex.use_rgb_to_intensity = True


    def buildEmission(self, mat):
        channel = self.getChannelEmissionColor()
        if channel:
            color = Vector(self.getChannelColor(channel, BLACK))
            strength = color.length/math.sqrt(3)
            if (strength > 0.001 or
                self.hasTextures(channel)):
                mat.emit = strength
                mat.diffuse_color = color
                for mtex in self.buildMtexs(channel, "sRGB", color):
                    if mtex and not mtex.use_stencil:
                        mtex.use_map_emit = True
                        mtex.emit_factor = strength
                        mtex.use_map_diffuse = True
                        mtex.diffuse_color_factor = 1.0

#-------------------------------------------------------------
#   Bump and normal
#-------------------------------------------------------------

    def buildNormal(self, mat):
        channel = self.getChannelNormal()
        if channel:
            for mtex in self.buildMtexs(channel, "Non-Color"):
                if mtex and not mtex.use_stencil:
                    self.setNormalSettings(channel, mtex)
            for shell,uv in self.shells:
                continue
                mtex = self.buildShellMTex(shell, "getChannelNormal", uv, "Non-Color")
                if mtex:
                    shell.setNormalSettings(channel, mtex)


    def setNormalSettings(self, channel, mtex):
        mtex.use_map_normal = True
        mtex.normal_factor = self.getChannelValue(channel, 1)
        tex = mtex.texture
        if tex:
            tex.use_normal_map = True
        mtex.normal_map_space = 'TANGENT'


    def buildBump(self, mat):
        channel = self.getChannelBump()
        if channel:
            for mtex in self.buildMtexs(channel, "Non-Color"):
                if mtex and not mtex.use_stencil:
                    self.setBumpSettings(channel, mtex)
            for shell,uv in self.shells:
                continue
                mtex = self.buildShellMTex(shell, "getChannelBump", uv, "Non-Color")
                if mtex:
                    shell.setBumpSettings(channel, mtex)


    def setBumpSettings(self, channel, mtex):
        mtex.use_map_normal = True
        mtex.normal_factor = self.getChannelValue(channel, 1)
        mtex.use_rgb_to_intensity = True
        mtex.bump_method = 'BUMP_ORIGINAL'


    def buildDisplacement(self, mat):
        channel = self.getChannelDisplacement()
        if channel:
            for mtex in self.buildMtexs(channel, "Non-Color"):
                if mtex and not mtex.use_stencil:
                    self.setDisplacementSettings(channel, mtex)
                    mat.DazUseDisplacement = True
            for shell,uv in self.shells:
                continue
                mtex = self.buildShellMTex(shell, "getChannelDisplacement", uv, "Non-Color")
                if mtex:
                    shell.setDisplacementSettings(channel, mtex)
                    mat.DazUseDisplacement = True


    def setDisplacementSettings(self, channel, mtex):
        mtex.use_map_displacement = True
        mtex.displacement_factor = theSettings.scale * self.getChannelValue(channel, 1)
        mtex.use_rgb_to_intensity = True

#-------------------------------------------------------------
#   Transparency
#-------------------------------------------------------------

    def buildTransparency(self, mat):
        channel,alpha,cutout,guessed,refract,imgfile = self.getAlphaChannel(mat)
        if channel:
            mat.alpha = alpha
            mtexs = self.buildMtexs(channel, "Non-Color")
            for mtex in mtexs:
                if mtex and not mtex.use_stencil:
                    mtex.use_map_alpha = True
                    mtex.alpha_factor = 1
                    mtex.use_rgb_to_intensity = True
                    mtex.invert = refract
            if mtexs:
                mat.use_transparency = True
                mat.alpha = 0
                mat.specular_alpha = 0
            elif mat.alpha < 1:
                mat.use_transparency = True


    def hasTransparency(self):
        return (self.getChannelRefractionStrength() or
                self.getChannelOpacity() or
                self.getChannelCutoutOpacity())


    def getAlphaChannel(self, mat):
        from .guess import castsShadow
        refractChannel = self.getChannelRefractionStrength()
        opacityChannel = self.getChannelOpacity()
        cutoutChannel = self.getChannelCutoutOpacity()
        alpha = 1
        channel = None
        refract = False
        cutout = False
        imgfile = None
        guessed = False
        done = False

        if cutoutChannel:
            alpha = self.getChannelValue(cutoutChannel, 1.0)
            imgfile = self.getImageFile(cutoutChannel)
            if imgfile:
                done = True
                channel = cutoutChannel
                cutout = True
        if not done and refractChannel:
            alpha = 1 - self.getChannelValue(refractChannel, 0.0)
            imgfile = self.getImageFile(refractChannel)
            if alpha < 1 or imgfile:
                done = True
                channel = refractChannel
                refract = True
        if not done and opacityChannel:
            alpha = self.getChannelValue(opacityChannel, 1.0)
            imgfile = self.getImageFile(opacityChannel)
            channel = opacityChannel
        if not castsShadow(mat):
            #alpha = 0
            guessed = True

        return channel, alpha, cutout, guessed, refract, imgfile


    def buildMtexs(self, channel, colorspace, color=WHITE):
        from .material import isWhite
        if not isWhite(color):
            color = self.getChannelValue(channel, WHITE)
        else:
            color = None
        mtexs = []
        ismask = False
        assets,maps = self.getTextures(channel)
        for idx,asset in enumerate(assets):
            map = maps[idx]
            asset.buildInternal()
            tex = asset.rna
            self.setColorSpace(tex, channel, colorspace)
            mtex = self.buildMtex(asset, color)
            if asset.hasMapping(map):
                map.rotation = 0
                dx,dy,sx,sy,rz = asset.getMapping(self, map)
                if (sx != 1 or sy != 1 or dx != 0 or dy != 0 or rz != 0):
                    mtex.offset[0] = dx
                    mtex.offset[1] = dy
                    mtex.scale[0] = 1/sx
                    mtex.scale[1] = 1/sy
                    tex.extension = 'CLIP'
            mtex.invert = map.invert
            if ismask:
                mtex.blend_type = 'MULTIPLY'
            mtexs.append(mtex)
            ismask = mtex.use_stencil
            if tex and ismask:
                setImageColorSpace(tex.image, "Non-Color")
        return mtexs


    def setColorSpace(self, tex, channel, default):
        if tex is None:
            return
        gamma = self.getGamma(channel)
        if gamma == 0:
            colorspace = default
        elif gamma == 1:
            colorspace = "Non-Color"
        colorspace = default
        if tex.type == 'IMAGE':
            setImageColorSpace(tex.image, colorspace)


    def buildMtex(self, asset, color):
        mat = self.rna
        mtex = mat.texture_slots.add()
        tex = asset.rna
        if tex and color:
            tex = tex.copy()
            tex.factor_red, tex.factor_green, tex.factor_blue = color
        mtex.texture = tex
        mtex.use_map_color_diffuse = False
        mtex.texture_coords = 'UV'
        if asset.map.ismask:
            mtex.use_stencil = True
            mtex.use_rgb_to_intensity = True
        op = asset.map.operation
        if op == "multiply":
            mtex.blend_type = 'MULTIPLY'
        elif op != "alpha_blend":
            print("MIX", asset, asset.map.operation)
        return mtex

