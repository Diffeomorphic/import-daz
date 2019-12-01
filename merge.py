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


import os
import json
import bpy
from bpy.props import *
from .utils import *
from .error import *
from .settings import theSettings

#-------------------------------------------------------------
#   Merge meshes
#-------------------------------------------------------------

def joinUvTextures(me, keep):
    if len(me.uv_layers) <= 1:
        return
    for n,data in enumerate(me.uv_layers[0].data):
        if data.uv.length < 1e-6:
            for uvloop in me.uv_layers[1:]:
                if uvloop.data[n].uv.length > 1e-6:
                    data.uv = uvloop.data[n].uv
                    break
    for uvtex in list(getUvTextures(me)[1:]):
        if uvtex.name not in keep:
            try:
                getUvTextures(me).remove(uvtex)
            except RuntimeError:
                print("Cannot remove texture layer '%s'" % uvtex.name)


def explicateUvTextures(me, uvname):
    if len(getUvTextures(me)) == 0:
        return
    uvtex = getUvTextures(me)[0]
    if uvname:
        oldname = uvtex.name
        newname = uvtex.name = uvname
    else:
        oldname = newname = uvtex.name
    for mat in me.materials:
        for mtex in mat.texture_slots:
            if mtex:
                if not mtex.uv_layer:
                    mtex.uv_layer = uvtex.name
        if mat.use_nodes:
            replaceNodeNames(mat, oldname, newname)


def getUvName(me):
    for uvtex in getUvTextures(me):
        if uvtex.active_render:
            return uvtex.name
    return None


def replaceNodeNames(mat, oldname, newname):
    for node in mat.node_tree.nodes:
        if isinstance(node, bpy.types.ShaderNodeAttribute):
            if node.attribute_name == oldname:
                node.attribute_name = newname
        elif isinstance(node, bpy.types.ShaderNodeNormalMap):
            if node.uv_map == oldname:
                node.uv_map = newname


def copyMaterial(cob, aob):
    torso = None
    for mat in cob.data.materials:
        if mat.name[0:5] == "Torso":
            torso = mat
            break
    mat = aob.data.materials[0]
    if torso and mat:
        mat.diffuse_color = torso.diffuse_color
        mat.diffuse_intensity = torso.diffuse_intensity
        mat.specular_color = torso.specular_color
        mat.specular_intensity = torso.specular_intensity
        mat.specular_hardness = torso.specular_hardness
        mtex = mat.texture_slots[0]
        if mtex is None:
            for tmtex in torso.texture_slots:
                if tmtex is None:
                    break
                mtex = mat.texture_slots.add()
                mtex.texture = tmtex.texture


def mergeAnatomy(context):
    from .driver import getShapekeyDrivers, copyShapeKeyDrivers

    bpy.ops.object.mode_set(mode='OBJECT')
    cob = context.object
    if cob.data.DazGraftGroup:
        raise DazError("Meshes selected in wrong order.\nAnatomies selected and body active.   ")

    # Find anatomies and move graft verts into position
    anatomies = []
    for aob in getSceneObjects(context):
        if (aob.type == 'MESH' and
            getSelected(aob) and
            aob != cob and
            aob.data.DazGraftGroup):
            anatomies.append(aob)

    if len(anatomies) < 1:
        raise DazError("At least two meshes must be selected.\nAnatomy selected and body active.")

    cname = getUvName(cob.data)
    anames = []
    keep = []
    drivers = {}

    # Select graft group for each anatomy
    for aob in anatomies:
        activateObject(context, aob)
        moveGraftVerts(aob, cob)
        getShapekeyDrivers(aob, drivers)
        for uvtex in getUvTextures(aob.data):
            if uvtex.active_render:
                anames.append(uvtex.name)
            else:
                keep.append(uvtex.name)

    # For the body, delete mask groups
    activateObject(context, cob)
    nverts = len(cob.data.vertices)
    deleted = dict([(vn,False) for vn in range(nverts)])
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')
    for aob in anatomies:
        graft = [pair.b for pair in aob.data.DazGraftGroup]
        for face in aob.data.DazMaskGroup:
            for vn in cob.data.polygons[face.a].vertices:
                if vn not in graft:
                    cob.data.vertices[vn].select = True
                    deleted[vn] = True

    assoc = {}
    vn2 = 0
    for vn in range(nverts):
        if not deleted[vn]:
            assoc[vn] = vn2
            vn2 += 1

    # Select verts on common boundary
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.delete(type='VERT')
    bpy.ops.object.mode_set(mode='OBJECT')
    for aob in anatomies:
        activateObject(context, aob)
        for pair in aob.data.DazGraftGroup:
            aob.data.vertices[pair.a].select = True
            cvn = assoc[pair.b]
            cob.data.vertices[cvn].select = True

    # Join meshes and remove doubles
    activateObject(context, cob)
    names = []
    for aob in anatomies:
        setSelected(aob, True)
        names.append(aob.name)
    print("Merge %s to %s" % (names, cob.name))
    bpy.ops.object.join()
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.remove_doubles(threshold=0.001*cob.DazScale)
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    joinUvTextures(cob.data, keep)

    newname = getUvName(cob.data)
    for mat in cob.data.materials:
        if mat.use_nodes:
            replaceNodeNames(mat, cname, newname)
            for aname in anames:
                replaceNodeNames(mat, aname, newname)

    copyShapeKeyDrivers(cob, drivers)
    updateDrivers(cob)


def moveGraftVerts(aob, cob):
    for pair in aob.data.DazGraftGroup:
        aob.data.vertices[pair.a].co = cob.data.vertices[pair.b].co
    if cob.data.shape_keys and aob.data.shape_keys:
        for cskey in cob.data.shape_keys.key_blocks:
            if cskey.name in aob.data.shape_keys.key_blocks.keys():
                askey = aob.data.shape_keys.key_blocks[cskey.name]
                for pair in aob.data.DazGraftGroup:
                    askey.data[pair.a].co = cskey.data[pair.b].co


class DAZ_OT_MergeAnatomy(bpy.types.Operator):
    bl_idname = "daz.merge_anatomy"
    bl_label = "Merge Anatomy"
    bl_description = "Merge selected anatomy to selected character"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

    def execute(self, context):
        try:
            mergeAnatomy(context)
        except DazError as err:
            handleDazError(context)
        return{'FINISHED'}

#-------------------------------------------------------------
#   Create graft and mask vertex groups
#-------------------------------------------------------------

class DAZ_OT_CreateGraftGroups(bpy.types.Operator):
    bl_idname = "daz.create_graft_groups"
    bl_label = "Greate Graft Groups"
    bl_description = "Create vertex groups from graft information"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.data.DazGraftGroup)

    def execute(self, context):
        try:
            self.createGroups(context)
        except DazError as err:
            handleDazError(context)
        return{'FINISHED'}


    def createGroups(self, context):
        aob = context.object
        objects = []
        for ob in getSceneObjects(context):
            if (ob.type == 'MESH' and
                getSelected(ob) and
                ob != aob):
                objects.append(ob)
        if len(objects) != 1:
            raise DazError("Exactly two meshes must be selected.    ")
        cob = objects[0]
        gname = "Graft_" + aob.data.name
        mname = "Mask_" + aob.data.name
        createVertexGroup(aob, gname, [pair.a for pair in aob.data.DazGraftGroup])
        graft = [pair.b for pair in aob.data.DazGraftGroup]
        createVertexGroup(cob, gname, graft)
        mask = {}
        for face in aob.data.DazMaskGroup:
            for vn in cob.data.polygons[face.a].vertices:
                if vn not in graft:
                    mask[vn] = True
        createVertexGroup(cob, mname, mask.keys())


def createVertexGroup(ob, gname, vnums):
    vgrp = ob.vertex_groups.new(name=gname)
    for vn in vnums:
        vgrp.add([vn], 1, 'REPLACE')
    return vgrp

#-------------------------------------------------------------
#   Merge UV sets
#-------------------------------------------------------------

def joinActiveToRender(me):
    actIdx = rndIdx = 0
    for n,uvtex in enumerate(getUvTextures(me).values()):
        if uvtex.active:
            actIdx = n
        if uvtex.active_render:
            rndIdx = n
    if actIdx == rndIdx:
        raise DazError("Active and render UV textures are equal")
    render = me.uv_layers[rndIdx]
    for n,data in enumerate(me.uv_layers[actIdx].data):
        if data.uv.length > 1e-6:
            render.data[n].uv = data.uv
    uvtex = getUvTextures(me).active
    getUvTextures(me).active_index = rndIdx
    getUvTextures(me).remove(uvtex)
    print("UV layers joined")


class DAZ_OT_MergeUVLayers(bpy.types.Operator):
    bl_idname = "daz.merge_uv_layers"
    bl_label = "Merge UV Layers"
    bl_description = "Merge active UV layer with render UV layer"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

    def execute(self, context):
        try:
            joinActiveToRender(context.object.data)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')
        except DazError as err:
            handleDazError(context)
        return{'FINISHED'}


#-------------------------------------------------------------
#   Merge armatures
#-------------------------------------------------------------

def addToGroups(ob, groups):
    for grp in groups:
        if ob.name not in grp.objects:
            grp.objects.link(ob)


def changeArmatureModifier(ob, rig, context):
    from .node import setParent
    setParent(context, ob, rig)
    if ob.parent_type != 'BONE':
        for mod in ob.modifiers:
            if mod.type == "ARMATURE":
                mod.name = rig.name
                mod.object = rig
                return
        mod = ob.modifiers.new(rig.name, "ARMATURE")
        mod.object = rig
        mod.use_deform_preserve_volume = True


def setRestPose(ob, rig, context):
    from .node import setParent
    setActiveObject(context, ob)
    setParent(context, ob, rig)
    if ob.parent_type == 'BONE' or ob.type != 'MESH':
        return

    if theSettings.fitFile:
        for mod in ob.modifiers:
            if mod.type == 'ARMATURE':
                mod.object = rig
    else:
        for mod in ob.modifiers:
            if mod.type == 'ARMATURE':
                mname = mod.name
                if ob.data.shape_keys:
                    bpy.ops.object.modifier_apply(apply_as='SHAPE', modifier=mname)
                    skey = ob.data.shape_keys.key_blocks[mname]
                    skey.value = 1.0
                else:
                    bpy.ops.object.modifier_apply(apply_as='DATA', modifier=mname)
        mod = ob.modifiers.new(rig.name, "ARMATURE")
        mod.object = rig
        mod.use_deform_preserve_volume = True
        nmods = len(ob.modifiers)
        for n in range(nmods-1):
            bpy.ops.object.modifier_move_up(modifier=mod.name)


def getSelectedRigs(context):
    rig = context.object
    if rig:
        bpy.ops.object.mode_set(mode='OBJECT')
    subrigs = []
    for ob in getSceneObjects(context):
        if getSelected(ob) and ob.type == 'ARMATURE' and ob != rig:
            subrigs.append(ob)
    groups = getGroups(context, rig)
    return rig, subrigs, groups

#-------------------------------------------------------------
#   Copy poses
#-------------------------------------------------------------

class DAZ_OT_CopyPoses(bpy.types.Operator):
    bl_idname = "daz.copy_poses"
    bl_label = "Copy Poses"
    bl_description = "Copy selected rig poses to active rig"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'ARMATURE')

    def execute(self, context):
        try:
            self.copyPoses(context)
        except DazError as err:
            handleDazError(context)
        return{'FINISHED'}


    def copyPoses(self, context):
        rig,subrigs,_groups = getSelectedRigs(context)
        if rig is None:
            print("No poses to copy")
            return

        print("Copy pose to %s:" % rig.name)
        for ob in subrigs:
            print("  ", ob.name)
            setActiveObject(context, rig)

            # L_b = R^-1_b R_p M^-1_p M_b
            for cb in ob.pose.bones:
                if cb.name in rig.pose.bones:
                    pb = rig.pose.bones[cb.name]
                    mat = cb.matrix.copy()
                    mat.col[3] = pb.matrix.col[3]
                    mat = Mult2(ob.matrix_world.inverted(), mat)
                    par = pb.parent
                    if par:
                        mat = Mult3(par.bone.matrix_local, par.matrix.inverted(), mat)
                    mat = Mult2(pb.bone.matrix_local.inverted(), mat)
                    pb.matrix_basis = mat
                    toggleEditMode()

        setActiveObject(context, rig)

#-------------------------------------------------------------
#   Merge rigs
#-------------------------------------------------------------

class DAZ_OT_MergeRigs(bpy.types.Operator):
    bl_idname = "daz.merge_rigs"
    bl_label = "Merge Rigs"
    bl_description = "Merge selected rigs to active rig"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'ARMATURE')

    def execute(self, context):
        try:
            rig,subrigs,groups = getSelectedRigs(context)
            theSettings.forAnimation(None, rig, context.scene)
            self.mergeRigs(rig, subrigs, context, groups)
        except DazError as err:
            handleDazError(context)
        return{'FINISHED'}


    def mergeRigs(self, rig, subrigs, context, groups):
        if rig is None:
            print("No rigs to merge")
            return
        oldvis = list(rig.data.layers)
        rig.data.layers = 32*[True]
        try:
            self.mergeRigs1(rig, subrigs, context, groups)
        finally:
            rig.data.layers = oldvis
            setActiveObject(context, rig)


    def mergeRigs1(self, rig, subrigs, context, groups):
        from .proxy import stripName
        from .node import clearParent
        scn = context.scene

        meshes = []
        for ob in getSceneObjects(context):
            if ob.type in 'MESH':
                if ob.data in meshes:
                    ob.data = ob.data.copy()
                else:
                    meshes.append(ob.data)

        print("Merge rigs to %s:" % rig.name)
        for ob in rig.children:
            if ob.type == 'MESH':
                changeArmatureModifier(ob, rig, context)
                addToGroups(ob, groups)

        self.mainBones = [bone.name for bone in rig.data.bones]
        for subrig in subrigs:
            success = True
            if (subrig.parent and
                subrig.parent_type == 'BONE'):
                parbone = subrig.parent_bone
                clearParent(subrig)
            else:
                parbone = None

            if success:
                print("  ", subrig.name, parbone)
                storage = self.addExtraBones(subrig, rig, context, scn, parbone)

                for ob in subrig.children:
                    if ob.type == 'MESH':
                        changeArmatureModifier(ob, rig, context)
                        changeVertexGroupNames(ob, storage)
                        addToGroups(ob, groups)
                        ob.name = stripName(ob.name)
                        ob.data.name = stripName(ob.data.name)
                        ob.parent = rig

                subrig.parent = None
                deleteObject(context, subrig)

        activateObject(context, rig)
        bpy.ops.object.mode_set(mode='OBJECT')


    def addExtraBones(self, ob, rig, context, scn, parbone):
        from .figure import copyBoneInfo
        extras = []
        for bone in ob.data.bones:
            if (bone.name not in self.mainBones or
                bone.name not in rig.data.bones.keys()):
                extras.append(bone.name)

        if extras:
            storage = {}
            activateObject(context, ob)
            try:
                bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            except RuntimeError:
                pass

            bpy.ops.object.mode_set(mode='EDIT')
            for bname in extras:
                eb = ob.data.edit_bones[bname]
                storage[bname] = EditBoneStorage(eb, None)
            bpy.ops.object.mode_set(mode='OBJECT')

            setActiveObject(context, rig)
            layers = (scn.DazClothesLayer-1)*[False] + [True] + (32-scn.DazClothesLayer)*[False]
            bpy.ops.object.mode_set(mode='EDIT')
            for bname in extras:
                eb = storage[bname].createBone(rig, storage, parbone)
                eb.layers = layers
                storage[bname].realname = eb.name
            bpy.ops.object.mode_set(mode='OBJECT')
            for bname in extras:
                copyBoneInfo(ob.data.bones[bname], rig.data.bones[bname])

            return storage
        else:
            return {}


def changeVertexGroupNames(ob, storage):
    for bname in storage.keys():
        if bname in ob.vertex_groups.keys():
            vgrp = ob.vertex_groups[bname]
            vgrp.name = storage[bname].realname

#-------------------------------------------------------------
#   Copy bone locations
#-------------------------------------------------------------

def copyBones(rig, subrigs, context):
    if rig is None:
        print("No bones to copy")
        return

    print("Copy bones to %s:" % rig.name)
    ebones = []
    for ob in subrigs:
        print("  ", ob.name)
        setActiveObject(context, ob)
        bpy.ops.object.mode_set(mode='EDIT')
        for eb in ob.data.edit_bones:
            ebones.append(EditBoneStorage(eb))
        bpy.ops.object.mode_set(mode='POSE')

    setActiveObject(context, rig)
    bpy.ops.object.mode_set(mode='EDIT')
    for storage in ebones:
        storage.copyBoneLocation(rig)
    bpy.ops.object.mode_set(mode='POSE')


class DAZ_OT_CopyBones(bpy.types.Operator):
    bl_idname = "daz.copy_bones"
    bl_label = "Copy Bones"
    bl_description = "Copy selected rig bone locations to active rig"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'ARMATURE')

    def execute(self, context):
        try:
            rig,subrigs,groups = getSelectedRigs(context)
            copyBones(rig, subrigs, context)
        except DazError as err:
            handleDazError(context)
        return{'FINISHED'}

#-------------------------------------------------------------
#   Apply rest pose
#-------------------------------------------------------------


class DAZ_OT_ApplyRestPoses(bpy.types.Operator):
    bl_idname = "daz.apply_rest_pose"
    bl_label = "Apply Rest Pose"
    bl_description = "Apply current pose at rest pose to selected rigs and children"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'ARMATURE')

    def execute(self, context):
        try:
            applyRestPoses(context)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}


def applyRestPoses(context):
    scn = context.scene
    rig,subrigs,_groups = getSelectedRigs(context)
    theSettings.forAnimation(None, rig, scn)
    rigs = [rig] + subrigs
    for subrig in rigs:
        for ob in subrig.children:
            if ob.type == 'MESH':
                setRestPose(ob, subrig, context)
        setActiveObject(context, subrig)
        bpy.ops.object.mode_set(mode='POSE')
        bpy.ops.pose.armature_apply()
    setActiveObject(context, rig)

#-------------------------------------------------------------
#   Merge toes
#-------------------------------------------------------------

GenesisToes = {
    "lFoot" : ["lMetatarsals"],
    "rFoot" : ["rMetatarsals"],
    "lToe" : ["lBigToe", "lSmallToe1", "lSmallToe2", "lSmallToe3", "lSmallToe4",
              "lBigToe_2", "lSmallToe1_2", "lSmallToe2_2", "lSmallToe3_2", "lSmallToe4_2"],
    "rToe" : ["rBigToe", "rSmallToe1", "rSmallToe2", "rSmallToe3", "rSmallToe4",
              "rBigToe_2", "rSmallToe1_2", "rSmallToe2_2", "rSmallToe3_2", "rSmallToe4_2"],
}

NewParent = {
    "lToe" : "lFoot",
    "rToe" : "rFoot",
}


def reparentToes(rig, context):
    setActiveObject(context, rig)
    bpy.ops.object.mode_set(mode='EDIT')
    for parname in ["lToe", "rToe"]:
        if parname in rig.data.edit_bones.keys():
            parb = rig.data.edit_bones[parname]
            for bname in GenesisToes[parname]:
                if bname[-2:] == "_2":
                    continue
                if bname in rig.data.edit_bones.keys():
                    eb = rig.data.edit_bones[bname]
                    eb.parent = parb
    bpy.ops.object.mode_set(mode='OBJECT')


class DAZ_OT_ReparentToes(bpy.types.Operator):
    bl_idname = "daz.reparent_toes"
    bl_label = "Reparent Toes"
    bl_description = "Parent small toes to big toe bone"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'ARMATURE')

    def execute(self, context):
        try:
            reparentToes(context.object, context)
        except DazError as err:
            handleDazError(context)
        return{'FINISHED'}


def mergeBonesAndVgroups(rig, mergers, parents, context):
    from .mhx import doHardUpdate
    from .driver import removeBoneDrivers

    activateObject(context, rig)
    
    bpy.ops.object.mode_set(mode='OBJECT')
    for bones in mergers.values():
        removeBoneDrivers(rig, bones)

    bpy.ops.object.mode_set(mode='EDIT')
    for bname,pname in parents.items():
        if (pname in rig.data.edit_bones.keys() and
            bname in rig.data.edit_bones.keys()):
            eb = rig.data.edit_bones[bname]
            parb = rig.data.edit_bones[pname]
            eb.use_connect = False
            eb.parent = parb
            parb.tail = eb.head

    for bones in mergers.values():
        for eb in rig.data.edit_bones:
            if eb.name in bones:
                rig.data.edit_bones.remove(eb)

    bpy.ops.object.mode_set(mode='OBJECT')

    for ob in rig.children:
        if ob.type == 'MESH':
            for toe,subtoes in mergers.items():
                if toe in ob.vertex_groups.keys():
                    vgrp = ob.vertex_groups[toe]
                else:
                    vgrp = ob.vertex_groups.new(name=toe)
                subgrps = []
                for subtoe in subtoes:
                    if subtoe in ob.vertex_groups.keys():
                        subgrps.append(ob.vertex_groups[subtoe])
                idxs = [vg.index for vg in subgrps]
                idxs.append(vgrp.index)
                weights = dict([(vn,0) for vn in range(len(ob.data.vertices))])
                for v in ob.data.vertices:
                    for g in v.groups:
                        if g.group in idxs:
                            weights[v.index] += g.weight
                for subgrp in subgrps:
                    ob.vertex_groups.remove(subgrp)
                for vn,w in weights.items():
                    if w > 1e-3:
                        vgrp.add([vn], w, 'REPLACE')

    doHardUpdate(context, rig)
    bpy.ops.object.mode_set(mode='OBJECT')


class DAZ_OT_MergeToes(bpy.types.Operator):
    bl_idname = "daz.merge_toes"
    bl_label = "Merge Toes"
    bl_description = "Merge all toes"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'ARMATURE')

    def execute(self, context):
        try:
            rig = context.object
            mergeBonesAndVgroups(rig, GenesisToes, NewParent, context)
        except DazError as err:
            handleDazError(context)
        return{'FINISHED'}


#-------------------------------------------------------------
#   EditBoneStorage
#-------------------------------------------------------------

class EditBoneStorage:
    def __init__(self, eb, pname=None):
        self.name = eb.name
        self.realname = self.name
        self.head = eb.head.copy()
        self.tail = eb.tail.copy()
        self.roll = eb.roll
        if eb.parent:
            self.parent = eb.parent.name
        else:
            self.parent = pname


    def createBone(self, rig, storage, parbone):
        eb = rig.data.edit_bones.new(self.name)
        self.realname = eb.name
        eb.head = self.head
        eb.tail = self.tail
        eb.roll = self.roll
        if storage and self.parent in storage.keys():
            pname = storage[self.parent].realname
        elif self.parent:
            pname = self.parent
        elif parbone:
            pname = parbone
        else:
            pname = None

        if pname is not None:
            eb.parent = rig.data.edit_bones[pname]
        return eb


    def copyBoneLocation(self, rig):
        if self.name in rig.data.edit_bones:
            eb = rig.data.edit_bones[self.name]
            eb.head = self.head
            eb.tail = self.tail
            eb.roll = self.roll

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_MergeAnatomy,
    DAZ_OT_CreateGraftGroups,
    DAZ_OT_MergeUVLayers,
    DAZ_OT_CopyPoses,
    DAZ_OT_MergeRigs,
    DAZ_OT_CopyBones,
    DAZ_OT_ApplyRestPoses,
    DAZ_OT_ReparentToes,
    DAZ_OT_MergeToes,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
