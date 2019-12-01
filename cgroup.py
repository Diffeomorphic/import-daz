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

from .cycles import CyclesTree
from .pbr import PbrTree
from .material import WHITE

# ---------------------------------------------------------------------
#   CyclesGroup
# ---------------------------------------------------------------------

class MaterialGroup:
    def __init__(self, node, name, parent, ncols):
        self.group = bpy.data.node_groups.new(name, 'ShaderNodeTree')
        node.node_tree = self.group
        self.nodes = self.group.nodes
        self.links = self.group.links
        self.inputs = self.addNode(0, "NodeGroupInput")
        self.outputs = self.addNode(ncols, "NodeGroupOutput")
        self.parent = parent


class CyclesGroup(MaterialGroup, CyclesTree):
    def __init__(self, node, name, parent, ncols):
        CyclesTree.__init__(self, parent.material)
        MaterialGroup.__init__(self, node, name, parent, ncols)

# ---------------------------------------------------------------------
#   Shell Group
# ---------------------------------------------------------------------

class ShellGroup(MaterialGroup):

    def __init__(self, node, name, parent):
        MaterialGroup.__init__(self, node, name, parent, 7)
        self.group.inputs.new("NodeSocketShader", "Shader")
        self.group.inputs.new("NodeSocketVector", "UV")
        self.group.outputs.new("NodeSocketShader", "Shader")


    def addNodes(self, context, shell):
        shell.rna = self.parent.material.rna
        self.material = shell
        self.texco = self.inputs.outputs["UV"]
        self.buildLayer(context)
        alpha,tex = self.getColorTex("getChannelCutoutOpacity", "NONE", 1.0)
        mix = self.addNode(7, "ShaderNodeMixShader")
        mix.inputs[0].default_value = alpha
        if tex:
            self.links.new(tex.outputs[0], mix.inputs[0])
        self.links.new(self.inputs.outputs["Shader"], mix.inputs[1])
        self.links.new(self.active.outputs[0], mix.inputs[2])
        self.links.new(mix.outputs[0], self.outputs.inputs["Shader"])


class ShellCyclesGroup(ShellGroup, CyclesTree):
    def __init__(self, node, name, parent):
        CyclesTree.__init__(self, parent.material)
        ShellGroup.__init__(self, node, name, parent)


class ShellPbrGroup(ShellGroup, PbrTree):
    def __init__(self, node, name, parent):
        PbrTree.__init__(self, parent.material)
        ShellGroup.__init__(self, node, name, parent)


# ---------------------------------------------------------------------
#   Fresnel Group
# ---------------------------------------------------------------------

class FresnelGroup(CyclesGroup):

    def __init__(self, node, parent):
        CyclesGroup.__init__(self, node, "Fresnel", parent, 4)
        self.group.inputs.new("NodeSocketFloat", "IOR")
        self.group.inputs.new("NodeSocketFloat", "Roughness")
        self.group.inputs.new("NodeSocketVector", "Normal")
        self.group.outputs.new("NodeSocketFloat", "Fac")


    def addNodes(self):
        geo = self.addNode(1, "ShaderNodeNewGeometry")

        bump = self.addNode(1, "ShaderNodeBump")
        self.links.new(self.inputs.outputs["Normal"], bump.inputs["Normal"])
        bump.inputs["Strength"].default_value = 0

        mix1 = self.addNode(2, "ShaderNodeMixRGB")
        self.links.new(geo.outputs["Backfacing"], mix1.inputs["Fac"])
        self.links.new(self.inputs.outputs["IOR"], mix1.inputs[1])
        mix1.inputs[2].default_value[0:3] = WHITE

        mix2 = self.addNode(2, "ShaderNodeMixRGB")
        self.links.new(self.inputs.outputs["Roughness"], mix2.inputs["Fac"])
        self.links.new(bump.outputs[0], mix2.inputs[1])
        self.links.new(geo.outputs["Incoming"], mix2.inputs[2])

        fresnel = self.addNode(3, "ShaderNodeFresnel")
        self.links.new(mix1.outputs[0], fresnel.inputs["IOR"])
        self.links.new(mix2.outputs[0], fresnel.inputs["Normal"])
        self.links.new(fresnel.outputs["Fac"], self.outputs.inputs["Fac"])

# ---------------------------------------------------------------------
#   Dual Lobe Group
# ---------------------------------------------------------------------

class DualLobeGroup(CyclesGroup):

    def __init__(self, node, parent):
        CyclesGroup.__init__(self, node, "Dual Lobe BSDF", parent, 4)
        self.group.inputs.new("NodeSocketShader", "Shader")
        self.group.inputs.new("NodeSocketColor", "Color")
        self.group.inputs.new("NodeSocketFloat", "IOR")
        self.group.inputs.new("NodeSocketFloat", "Roughness 1")
        self.group.inputs.new("NodeSocketFloat", "Roughness 2")
        self.group.inputs.new("NodeSocketFloat", "Fac")
        self.group.inputs.new("NodeSocketVector", "Normal")
        self.group.outputs.new("NodeSocketShader", "BSDF")


    def addNodes(self):
        glossy1 = self.addGlossy("Roughness 1")
        glossy2 = self.addGlossy("Roughness 2")
        mix = self.addNode(3, "ShaderNodeMixShader")
        self.links.new(self.inputs.outputs["Fac"], mix.inputs[0])
        self.links.new(glossy1.outputs[0], mix.inputs[2])
        self.links.new(glossy2.outputs[0], mix.inputs[1])
        self.links.new(mix.outputs[0], self.outputs.inputs["BSDF"])


    def addGlossy(self, roughness):
        glossy = self.addNode(1, "ShaderNodeBsdfGlossy")
        self.links.new(self.inputs.outputs["Color"], glossy.inputs["Color"])
        self.links.new(self.inputs.outputs[roughness], glossy.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], glossy.inputs["Normal"])

        fresnel = self.addNode(1, "ShaderNodeGroup")
        group = FresnelGroup(fresnel, self)
        group.addNodes()
        self.links.new(self.inputs.outputs["IOR"], fresnel.inputs["IOR"])
        self.links.new(self.inputs.outputs[roughness], fresnel.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], fresnel.inputs["Normal"])

        mix = self.addNode(2, "ShaderNodeMixShader")
        self.links.new(fresnel.outputs[0], mix.inputs[0])
        self.links.new(self.inputs.outputs["Shader"], mix.inputs[1])
        self.links.new(glossy.outputs[0], mix.inputs[2])
        return mix

# ---------------------------------------------------------------------
#   Displacement Group
# ---------------------------------------------------------------------

class DisplacementGroup(CyclesGroup):

    def __init__(self, node, parent):
        CyclesGroup.__init__(self, node, "Diplacement Converter", parent, 4)
        self.group.inputs.new("NodeSocketFloat", "Texture")
        self.group.inputs.new("NodeSocketFloat", "Strength")
        self.group.inputs.new("NodeSocketFloat", "Difference")
        self.group.inputs.new("NodeSocketFloat", "Min")
        self.group.outputs.new("NodeSocketFloat", "Height")


    def addNodes(self):
        mult1 = self.addNode(1, "ShaderNodeMath")
        mult1.operation = 'MULTIPLY'
        self.links.new(self.inputs.outputs["Texture"], mult1.inputs[0])
        self.links.new(self.inputs.outputs["Difference"], mult1.inputs[1])
    
        add = self.addNode(2, "ShaderNodeMath")
        add.operation = 'ADD'
        self.links.new(mult1.outputs[0], add.inputs[0])
        self.links.new(self.inputs.outputs["Min"], add.inputs[1])
    
        mult2 = self.addNode(3, "ShaderNodeMath")
        mult2.operation = 'MULTIPLY'
        self.links.new(self.inputs.outputs["Strength"], mult2.inputs[0])
        self.links.new(add.outputs[0], mult2.inputs[1])
 
        self.links.new(mult2.outputs[0], self.outputs.inputs["Height"])
         
# ---------------------------------------------------------------------
#   Glass Group
# ---------------------------------------------------------------------

class GlassGroup(CyclesGroup):

    def __init__(self, node, parent):
        CyclesGroup.__init__(self, node, "MultiGlass", parent, 6)
        self.group.inputs.new("NodeSocketFloat", "ThinWall")
        self.group.inputs.new("NodeSocketColor", "RefractionColor")
        self.group.inputs.new("NodeSocketColor", "TransmissionColor")
        self.group.inputs.new("NodeSocketFloat", "RefractionRoughness")
        self.group.inputs.new("NodeSocketFloat", "IOR_trans")
        self.group.inputs.new("NodeSocketFloat", "GlossyLayeredWeight")
        self.group.inputs.new("NodeSocketColor", "GlossyColor")
        self.group.inputs.new("NodeSocketFloat", "GlossyRoughness")
        self.group.inputs.new("NodeSocketFloat", "IOR")
        self.group.inputs.new("NodeSocketVector", "Normal")

        self.group.outputs.new("NodeSocketShader", "Shader")
        self.group.outputs.new("NodeSocketShader", "Volume")


    def addNodes(self):
        transColor = self.addNode(2, "ShaderNodeMixRGB", "Trans Color")
        transColor.name = "TransColor"
        transColor.blend_type = 'MULTIPLY'
        transColor.inputs["Fac"].default_value = 1.0
        self.links.new(self.inputs.outputs["RefractionColor"], transColor.inputs[1])
        self.links.new(self.inputs.outputs["TransmissionColor"], transColor.inputs[2])

        power1 = self.addNode(1, "ShaderNodeMath")
        power1.operation = 'POWER'
        self.links.new(self.inputs.outputs["RefractionRoughness"], power1.inputs[0])
        power1.inputs[1].default_value = 2

        mono = self.addNode(1, "ShaderNodeMath", "Mono")
        mono.operation = 'MULTIPLY'
        self.links.new(self.inputs.outputs["GlossyLayeredWeight"], mono.inputs[0])
        mono.inputs[1].default_value = 1.0

        glossyColor = self.addNode(2, "ShaderNodeMixRGB", "Glossy Color")
        glossyColor.name = "GlossyColor"
        glossyColor.blend_type = 'MULTIPLY'
        glossyColor.inputs["Fac"].default_value = 1.0
        self.links.new(mono.outputs[0], glossyColor.inputs[1])
        self.links.new(self.inputs.outputs["GlossyColor"], glossyColor.inputs[2])

        power2 = self.addNode(1, "ShaderNodeMath")
        power2.operation = 'POWER'
        self.links.new(self.inputs.outputs["GlossyRoughness"], power2.inputs[0])
        power2.inputs[1].default_value = 2

        geo = self.addNode(3, "ShaderNodeNewGeometry")

        refraction = self.addNode(3, "ShaderNodeBsdfRefraction")
        refraction.distribution = 'GGX'
        self.links.new(transColor.outputs["Color"], refraction.inputs["Color"])
        self.links.new(power1.outputs[0], refraction.inputs["Roughness"])
        self.links.new(self.inputs.outputs["IOR_trans"], refraction.inputs["IOR"])
        self.links.new(self.inputs.outputs["Normal"], refraction.inputs["Normal"])

        fresnel = self.addNode(3, "ShaderNodeFresnel")
        self.links.new(self.inputs.outputs["IOR"], fresnel.inputs["IOR"])
        self.links.new(self.inputs.outputs["Normal"], fresnel.inputs["Normal"])

        glossy = self.addNode(3, "ShaderNodeBsdfGlossy")
        glossy.distribution = 'GGX'
        self.links.new(glossyColor.outputs["Color"], glossy.inputs["Color"])
        self.links.new(power2.outputs[0], glossy.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], glossy.inputs["Normal"])

        back = self.addNode(4, "ShaderNodeMath", "Backfacing")
        back.operation = 'MULTIPLY'
        self.links.new(geo.outputs["Backfacing"], back.inputs[0])
        self.links.new(self.inputs.outputs["ThinWall"], back.inputs[1])

        mix1 = self.addNode(4, "ShaderNodeMixShader")
        self.links.new(fresnel.outputs[0], mix1.inputs[0])
        self.links.new(refraction.outputs[0], mix1.inputs[1])
        self.links.new(glossy.outputs[0], mix1.inputs[2])

        mix2 = self.addNode(5, "ShaderNodeMixShader")
        self.links.new(back.outputs[0], mix2.inputs[0])
        self.links.new(mix1.outputs[0], mix2.inputs[1])
        self.links.new(refraction.outputs[0], mix2.inputs[2])

        self.links.new(mix2.outputs["Shader"], self.outputs.inputs["Shader"])

# ---------------------------------------------------------------------
#   Complex Glass Group
# ---------------------------------------------------------------------

class ComplexGlassGroup(CyclesGroup):

    def __init__(self, node, parent):
        CyclesGroup.__init__(self, node, "Complex MultiGlass", parent, 7)
        self.group.inputs.new("NodeSocketShader", "BaseShader")

        self.group.inputs.new("NodeSocketFloat", "RefractionWeight")
        self.group.inputs.new("NodeSocketFloat", "ThinWall")
        self.group.inputs.new("NodeSocketFloat", "IOR_trans")
        self.group.inputs.new("NodeSocketColor", "RefractionColor")
        self.group.inputs.new("NodeSocketFloat", "RefractionAdjust")
        self.group.inputs.new("NodeSocketFloat", "RefractionRoughness")

        self.group.inputs.new("NodeSocketFloat", "GlossyInput")
        self.group.inputs.new("NodeSocketFloat", "GlossyLayeredWeight")
        self.group.inputs.new("NodeSocketColor", "GlossyColor")
        self.group.inputs.new("NodeSocketFloat", "GlossyRoughness")

        self.group.inputs.new("NodeSocketFloat", "FresnelRoughness")
        self.group.inputs.new("NodeSocketFloat", "IOR")
        self.group.inputs.new("NodeSocketVector", "Normal")
        self.group.inputs.new("NodeSocketFloat", "RoughnessAdjust")

        self.group.inputs.new("NodeSocketColor", "TransmissionColor")
        self.group.inputs.new("NodeSocketFloat", "Density")

        self.group.outputs.new("NodeSocketShader", "Shader")
        self.group.outputs.new("NodeSocketShader", "Volume")


    def addNodes(self):
        thick = self.addNode(1, "ShaderNodeMath", "Thick")
        thick.operation = 'SUBTRACT'
        thick.inputs[0].default_value = 1.0
        self.links.new(self.inputs.outputs["ThinWall"], thick.inputs[1])

        iorTrans = self.addNode(1, "ShaderNodeMath", "Ior Trans")
        iorTrans.operation = 'MULTIPLY'
        self.links.new(self.inputs.outputs["ThinWall"], iorTrans.inputs[0])
        self.links.new(self.inputs.outputs["IOR_trans"], iorTrans.inputs[1])

        refrAdj = self.addNode(1, "ShaderNodeMath", "Refr Adjust")
        refrAdj.operation = 'MULTIPLY'
        refrAdj.inputs[0].default_value = 1.0
        self.links.new(self.inputs.outputs["RefractionAdjust"], refrAdj.inputs[1])

        glossyWeight = self.addNode(1, "ShaderNodeMath", "Glossy Weight")
        glossyWeight.operation = 'MULTIPLY'
        glossyWeight.inputs[0].default_value = 1.0
        self.links.new(self.inputs.outputs["GlossyLayeredWeight"], glossyWeight.inputs[1])

        gopSub = self.addNode(1, "ShaderNodeMath", "GopSub")
        gopSub.operation = 'SUBTRACT'
        gopSub.inputs[0].default_value = 1.0
        self.links.new(self.inputs.outputs["GlossyInput"], gopSub.inputs[1])

        refrRough = self.addNode(1, "ShaderNodeMath", "Refr Rough")
        refrRough.operation = 'POWER'
        self.links.new(self.inputs.outputs["RefractionRoughness"], refrRough.inputs[0])
        self.links.new(self.inputs.outputs["RefractionAdjust"], refrRough.inputs[1])

        glossyRough = self.addNode(1, "ShaderNodeMath", "Glossy Rough")
        glossyRough.operation = 'POWER'
        self.links.new(self.inputs.outputs["GlossyRoughness"], glossyRough.inputs[0])
        self.links.new(self.inputs.outputs["RefractionAdjust"], glossyRough.inputs[1])


        thickIor = self.addNode(2, "ShaderNodeMath", "Thick Ior")
        thickIor.operation = 'MULTIPLY'
        self.links.new(thick.outputs[0], thickIor.inputs[0])
        self.links.new(self.inputs.outputs["RefractionAdjust"], thickIor.inputs[1])

        transColor = self.addNode(2, "ShaderNodeMixRGB", "Trans Color")
        transColor.blend_type = 'MULTIPLY'
        self.links.new(self.inputs.outputs["GlossyInput"], transColor.inputs[0])
        self.links.new(self.inputs.outputs["RefractionColor"], transColor.inputs[1])
        self.links.new(self.inputs.outputs["TransmissionColor"], transColor.inputs[2])

        glossyColor = self.addNode(2, "ShaderNodeMixRGB", "Glossy Color")
        glossyColor.blend_type = 'MULTIPLY'
        glossyColor.inputs["Fac"].default_value = 1.0
        self.links.new(self.inputs.outputs["GlossyColor"], glossyColor.inputs[1])
        self.links.new(glossyWeight.outputs[0], glossyColor.inputs[2])

        gopRefr = self.addNode(2, "ShaderNodeMath", "GopRefr")
        gopRefr.operation = 'MULTIPLY'
        self.links.new(gopSub.outputs[0], gopRefr.inputs[0])
        self.links.new(refrRough.outputs[0], gopRefr.inputs[1])

        fresnelRough = self.addNode(2, "ShaderNodeMath", "Fresnel Rough")
        fresnelRough.operation = 'MULTIPLY'
        self.links.new(self.inputs.outputs["FresnelRoughness"], fresnelRough.inputs[0])
        self.links.new(glossyRough.outputs[0], fresnelRough.inputs[1])

        gopRough = self.addNode(2, "ShaderNodeMath", "GopRough")
        gopRough.operation = 'MULTIPLY'
        self.links.new(self.inputs.outputs["GlossyInput"], gopRough.inputs[0])
        self.links.new(glossyRough.outputs[0], gopRough.inputs[1])


        ior = self.addNode(3, "ShaderNodeMath", "IOR")
        ior.operation = 'ADD'
        self.links.new(thickIor.outputs[0], ior.inputs[0])
        self.links.new(iorTrans.outputs[0], ior.inputs[1])

        transColorMulti = self.addNode(3, "ShaderNodeMixRGB", "Trans Color Multi")
        transColorMulti.blend_type = 'MULTIPLY'
        transColorMulti.inputs["Fac"].default_value = 1.0
        self.links.new(transColor.outputs[0], transColorMulti.inputs[1])
        self.links.new(refrAdj.outputs[0], transColorMulti.inputs[2])

        #fresnel = self.addNode(3, "ShaderNodeFresnel")
        fresnel = self.addNode(3, "ShaderNodeGroup", "Fresnel")
        group = FresnelGroup(fresnel, self)
        group.addNodes()
        self.links.new(self.inputs.outputs["IOR"], fresnel.inputs["IOR"])
        self.links.new(fresnelRough.outputs[0], fresnel.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], fresnel.inputs["Normal"])

        glossy = self.addNode(3, "ShaderNodeBsdfGlossy")
        #glossy.distribution = 'GGX'
        self.links.new(glossyColor.outputs["Color"], glossy.inputs["Color"])
        self.links.new(glossyRough.outputs[0], glossy.inputs["Roughness"])
        self.links.new(self.inputs.outputs["Normal"], glossy.inputs["Normal"])

        gopOverRough = self.addNode(3, "ShaderNodeMath", "GopOverRough")
        gopOverRough.operation = 'ADD'
        self.links.new(gopRefr.outputs[0], gopOverRough.inputs[0])
        self.links.new(gopRough.outputs[0], gopOverRough.inputs[1])


        refraction = self.addNode(4, "ShaderNodeBsdfRefraction")
        refraction.distribution = 'GGX'
        self.links.new(transColorMulti.outputs["Color"], refraction.inputs["Color"])
        self.links.new(gopOverRough.outputs[0], refraction.inputs["Roughness"])
        self.links.new(ior.outputs[0], refraction.inputs["IOR"])
        self.links.new(self.inputs.outputs["Normal"], refraction.inputs["Normal"])

        volColor = self.addNode(4, "ShaderNodeMixRGB", "Volume Color")
        volColor.blend_type = 'MULTIPLY'
        volColor.inputs["Fac"].default_value = 1.0
        self.links.new(glossyWeight.outputs[0], volColor.inputs[1])
        self.links.new(transColorMulti.outputs[0], volColor.inputs[2])

        density = self.addNode(4, "ShaderNodeMath", "Density")
        density.operation = 'MULTIPLY'
        self.links.new(self.inputs.outputs["BaseShader"], density.inputs[0])
        self.links.new(self.inputs.outputs["Density"], density.inputs[1])

        mix1 = self.addNode(4, "ShaderNodeMixRGB", "Mix1")
        self.links.new(gopRough.outputs[0], mix1.inputs[0])
        self.links.new(transColorMulti.outputs[0], mix1.inputs[1])
        mix1.inputs[2].default_value[0:3] = (0,0,0)

        geo = self.addNode(4, "ShaderNodeNewGeometry")

        mix2 = self.addNode(5, "ShaderNodeMixShader", "Mix2")
        self.links.new(fresnel.outputs[0], mix2.inputs[0])
        self.links.new(refraction.outputs[0], mix2.inputs[1])
        self.links.new(glossy.outputs[0], mix2.inputs[2])

        volume = self.addNode(5, "ShaderNodeVolumeAbsorption")
        self.links.new(volColor.outputs[0], volume.inputs[0])
        self.links.new(density.outputs[0], volume.inputs[1])

        back = self.addNode(5, "ShaderNodeMath", "Backfacing")
        back.operation = 'MULTIPLY'
        self.links.new(geo.outputs["Backfacing"], back.inputs[0])
        self.links.new(self.inputs.outputs["ThinWall"], back.inputs[1])

        transparent = self.addNode(5, "ShaderNodeBsdfTransparent")
        self.links.new(mix1.outputs[0], transparent.inputs[0])

        light = self.addNode(5, "ShaderNodeLightPath")

        mix3 = self.addNode(6, "ShaderNodeMixShader", "mix3")
        self.links.new(back.outputs[0], mix3.inputs[0])
        self.links.new(mix2.outputs[0], mix3.inputs[1])
        self.links.new(refraction.outputs[0], mix3.inputs[2])

        mix4 = self.addNode(6, "ShaderNodeMixShader", "mix4")
        self.links.new(light.outputs["Is Shadow Ray"], mix4.inputs[0])
        self.links.new(mix3.outputs[0], mix4.inputs[1])
        self.links.new(transparent.outputs[0], mix4.inputs[2])

        mix5 = self.addNode(6, "ShaderNodeMixShader", "mix5")
        self.links.new(self.inputs.outputs["RefractionWeight"], mix5.inputs[0])
        self.links.new(self.inputs.outputs["BaseShader"], mix5.inputs[1])
        self.links.new(mix4.outputs[0], mix5.inputs[2])


        self.links.new(mix5.outputs["Shader"], self.outputs.inputs["Shader"])
        self.links.new(volume.outputs["Volume"], self.outputs.inputs["Volume"])

# ---------------------------------------------------------------------
#   LIE Group
# ---------------------------------------------------------------------

class LieGroup(CyclesGroup):

    def __init__(self, node, name, parent):
        CyclesGroup.__init__(self, node, name, parent, 6)
        self.group.inputs.new("NodeSocketVector", "Vector")
        self.texco = self.inputs.outputs[0]
        self.group.outputs.new("NodeSocketColor", "Color")


    def addTextureNodes(self, assets, maps, colorSpace):
        texnodes = []
        for idx,asset in enumerate(assets):
            texnode,isnew = self.addSingleTexture(3, asset, maps[idx], colorSpace)
            if isnew:
                innode = texnode
                mapping = self.mapTexture(asset, maps[idx])
                if mapping:
                    texnode.extension = 'CLIP'
                    self.links.new(mapping.outputs["Vector"], texnode.inputs["Vector"])
                    innode = mapping
                else:
                    self.setTexNode(asset.images[colorSpace].name, texnode, colorSpace)
                self.links.new(self.inputs.outputs["Vector"], innode.inputs["Vector"])
            texnodes.append([texnode])

        if texnodes:
            nassets = len(assets)
            for idx in range(1, nassets):
                map = maps[idx]
                if map.invert:
                    inv = self.addNode(4, "ShaderNodeInvert")
                    node = texnodes[idx][0]
                    self.links.new(node.outputs[0], inv.inputs["Color"])
                    texnodes[idx].append(inv)

            texnode = texnodes[0][-1]
            masked = False
            for idx in range(1, nassets):
                map = maps[idx]
                if map.ismask:
                    if idx == nassets-1:
                        continue
                    mix = self.addNode(5, "ShaderNodeMixRGB")    # ShaderNodeMixRGB
                    mix.blend_type = 'MULTIPLY'
                    mix.use_alpha = False
                    mask = texnodes[idx][-1]
                    self.setColorSpace(mask, 'NONE')
                    self.links.new(mask.outputs["Color"], mix.inputs[0])
                    self.links.new(texnode.outputs["Color"], mix.inputs[1])
                    self.links.new(texnodes[idx+1][-1].outputs["Color"], mix.inputs[2])
                    texnode = mix
                    masked = True
                elif not masked:
                    mix = self.addNode(5, "ShaderNodeMixRGB")
                    alpha = setMixOperation(mix, map)
                    mix.inputs[0].default_value = alpha
                    node = texnodes[idx][-1]
                    base = texnodes[idx][0]
                    if alpha != 1:
                        node = self.multiplyScalarTex(alpha, base, 4, "Alpha")
                        self.links.new(node.outputs[0], mix.inputs[0])
                    elif hasattr(base.outputs, "Alpha"):
                        self.links.new(base.outputs["Alpha"], mix.inputs[0])
                    else:
                        mix.inputs[0].default_value = alpha
                    mix.use_alpha = True
                    self.links.new(texnode.outputs["Color"], mix.inputs[1])
                    self.links.new(texnodes[idx][-1].outputs["Color"], mix.inputs[2])
                    texnode = mix
                    masked = False
                else:
                    masked = False

            self.links.new(texnode.outputs[0], self.outputs.inputs["Color"])


    def mapTexture(self, asset, map):
        if asset.hasMapping(map):
            data = asset.getMapping(self.material, map)
            return self.addMappingNode(data, map)


def setMixOperation(mix, map):
    alpha = 1
    op = map.operation
    alpha = map.transparency
    if op == "multiply":
        mix.blend_type = 'MULTIPLY'
        useAlpha = True
    elif op == "add":
        mix.blend_type = 'ADD'
        useAlpha = False
    elif op == "subtract":
        mix.blend_type = 'SUBTRACT'
        useAlpha = False
    elif op == "alpha_blend":
        mix.blend_type = 'MIX'
        useAlpha = True
    else:
        print("MIX", asset, map.operation)
    return alpha
