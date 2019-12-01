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
from random import random
from .utils import *
from .error import *

SkinMaterials = {
    "eyelash" : (0, ),
    "eyelashes" : (0, ),
    "eyemoisture" : (1, ),
    "lacrimal" : ("Red", ),
    "lacrimals" : ("Red", ),
    "cornea" : (0, ),
    "tear" : (1, ),
    "eyereflection" : (1, ),

    "fingernail" : ("Red", ),
    "fingernails" : ("Red", ),
    "toenail" : ("Red", ),
    "toenails" : ("Red", ),
    "lip" : ("Red", ),
    "lips" : ("Red", ),
    "mouth" : ("Red", ),
    "tongue" : ("Red", ),
    "innermouth" : ("Red", ),
    "gums" : ("Red", ),
    "teeth" : ("White", ),
    "pupil" : ("Black", ),
    "pupils" : ("Black", ),
    "sclera" : ("White", ),
    "iris" : ("Blue", ),
    "irises" : ("Blue", ),

    "skinface" : ("Skin", ),
    "face" : ("Skin", ),
    "nostril" : ("Skin", ),
    "nostrils" : ("Skin", ),
    "skinhead" : ("Skin", ),
    "eyebrow" : ("Skin", ),
    "head" : ("Skin", ),
    "ears" : ("Skin", ),
    "skinleg" : ("Skin", ),
    "legs" : ("Skin", ),
    "skintorso" : ("Skin", ),
    "torso" : ("Skin", ),
    "eyesocket" : ("Skin", ),
    "skinarm" : ("Skin", ),
    "arms" : ("Skin", ),
    "skinneck" : ("Skin", ),
    "neck" : ("Skin", ),
    "nipple" : ("Skin", ),
    "nipples" : ("Skin", ),
    "skinforearm" : ("Skin", ),
    "forearms" : ("Skin", ),
    "skinfoot" : ("Skin", ),
    "feet" : ("Skin", ),
    "skinhip" : ("Skin", ),
    "hips" : ("Skin", ),
    "shoulders" : ("Skin", ),
    "skinhand" : ("Skin", ),
    "hands" : ("Skin", ),

    "genitalia" : ("Skin", ),
    "labia" : ("Skin", ),
    "anus" : ("Skin", ),
    "vagina" : ("Skin", ),
}

def getSkinMaterial(mat):
    mname = mat.name.lower().split("-")[0].split(".")[0].split(" ")[0].split("&")[0]
    if mname in SkinMaterials.keys():
        return SkinMaterials[mname]
    mname2 = mname.rsplit("_", 2)[-1]
    if mname2 in SkinMaterials.keys():
        return SkinMaterials[mname2]
    return None


def castsShadow(mat):
    info = getSkinMaterial(mat)
    return (not (info and isinstance(info[0], int)))


def getMeshFromObject(ob):
    if isinstance(ob, bpy.types.Mesh):
        return ob
    elif (isinstance(ob, bpy.types.Object) and
          ob.type == 'MESH'):
        return ob.data
    else:
        return None


def setDiffuse(mat, color):
    mat.diffuse_color = color[0:len(mat.diffuse_color)]


def guessColor(ob, scn, flag, skinColor, clothesColor, enforce):
    from random import random
    if flag == 'WHITE':
        return
    me = getMeshFromObject(ob)
    if me is None:
        return

    for mat in me.materials:
        if not hasDiffuseTexture(mat, scn, enforce):
            continue

        elif flag == 'RANDOM':
            color = (random(), random(), random(), 1)
            setDiffuse(mat, color)

        elif flag in ['GUESS', 'GUESSRANDOM']:
            data = getSkinMaterial(mat)
            if data:
                color, = data
                if isinstance(color, int):
                    setDiffuse(mat, (color,color,color,1))
                else:
                    if color == "Skin":
                        setDiffuse(mat, skinColor)
                    elif color == "Red":
                        setDiffuse(mat, (1.0,0,0,1))
                    elif color == "Blue":
                        setDiffuse(mat, (0,0,1,1))
                    elif color == "White":
                        setDiffuse(mat, (1,1,1,1))
                    elif color == "Black":
                        setDiffuse(mat, (0,0,0,1))
            else:
                if flag == 'GUESS':
                    setDiffuse(mat, clothesColor)
                else:
                    setDiffuse(mat, (random(), random(), random(), 1))


def hasDiffuseTexture(mat, scn, enforce):
    from .material import isWhite
    if mat.node_tree:
        color = (1,1,1,1)
        node = None
        for node1 in mat.node_tree.nodes.values():
            if node1.type == "BSDF_DIFFUSE":
                node = node1
                name = "Color"
                break
            elif node1.type == "BSDF_PRINCIPLED":
                node = node1
                name = "Base Color"
                break
        if node is None:
            return True
        color = node.inputs[name].default_value
        if (not isWhite(color) and
            not enforce and
            scn.render.engine in ['BLENDER_RENDER', 'BLENDER_GAME']):
            setDiffuse(mat, color)
            return False
        for link in mat.node_tree.links:
            if (link.to_node == node and
                link.to_socket.name == name):
                return True
        setDiffuse(mat, color)
        return False
    else:
        if not isWhite(mat.diffuse_color) and not enforce:
            return False
        for mtex in mat.texture_slots:
            if mtex and mtex.use_map_color_diffuse:
                return True
        return False

#-------------------------------------------------------------
#   Change colors
#-------------------------------------------------------------

def changeColors(context, color, guess):
    scn = context.scene
    for ob in getSceneObjects(context):
        if getSelected(ob):
            if ob.type == 'ARMATURE':
                for child in ob.children:
                    if child.type == 'MESH':
                        changeMeshColor(child, scn, color, guess)
            elif ob.type == 'MESH':
                changeMeshColor(ob, scn, color, guess)


def changeMeshColor(ob, scn, color, guess):
    if guess:
        guessColor(ob, scn, 'GUESS', color, color, True)
    else:
        if scn.render.engine in ['BLENDER_RENDER', 'BLENDER_GAME']:
            for mat in ob.data.materials:
                for mtex in mat.texture_slots:
                    if mtex and mtex.use_map_color_diffuse:
                        setDiffuse(mat, color)
                        break
        else:
            for mat in ob.data.materials:
                setDiffuse(mat, color)


class DAZ_OT_ChangeColors(bpy.types.Operator):
    bl_idname = "daz.change_colors"
    bl_label = "Change Colors"
    bl_description = "Change viewport colors of all materials of this object"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

    def execute(self, context):
        try:
            changeColors(context, context.scene.DazNewColor, False)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}


class DAZ_OT_ChangeSkinColor(bpy.types.Operator):
    bl_idname = "daz.change_skin_color"
    bl_label = "Change Skin Colors"
    bl_description = "Change viewport colors of all materials of this object"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

    def execute(self, context):
        try:
            changeColors(context, context.scene.DazNewColor, True)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_ChangeColors,
    DAZ_OT_ChangeSkinColor,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)


