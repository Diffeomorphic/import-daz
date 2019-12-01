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
from bpy.props import *
#from .drivers import *
from .utils import *
from .error import *
if bpy.app.version < (2,80,0):
    from .buttons27 import PrefixString
else:
    from .buttons28 import PrefixString


def getMaskName(string):
    return "Mask_" + string.split(".",1)[0]

def getHidePropName(string):
    return "Mhh" + string.split(".",1)[0]

def getHideMannequinName():
    return "MhhMannequin"

#------------------------------------------------------------------------
#    Setup: Add and remove hide drivers
#------------------------------------------------------------------------

class HidersHandler:
    
    def execute(self, context):
        from .morphing import prettifyAll
        from .driver import updateAll
        rig = context.object
        for ob in self.getMeshesInGroup(context, rig):
            self.handleHideDrivers(ob, rig, context)
            setattr(ob, self.flag, self.value)
        setattr(rig, self.flag, self.value)
        prettifyAll(context)
        updateAll(context)
        setActiveObject(context, rig)
        return{'FINISHED'}


    def getMeshesInGroup(self, context, rig):        
        self.collection = None  
        meshes = list(rig.children)
        if bpy.app.version >= (2,80,0):
            for coll in bpy.data.collections:
                if rig in coll.all_objects.values():
                    for ob in meshes:
                        if ob in coll.all_objects.values():
                            self.collection = coll
                            return meshes
        return meshes


    def handleHideDrivers(self, clo, rig, context):
        if clo.DazMannequin:
            prop = getHideMannequinName()
            return
        else:
            prop = getHidePropName(clo.name)
        self.handleProp(prop, clo, rig, context)
        if clo.DazMannequin:
            return            
        modname = getMaskName(clo.name)
        for ob in rig.children:
            for mod in ob.modifiers:
                if (mod.type == 'MASK' and mod.name == modname):
                    self.handleMod(prop, rig, mod)


class DAZ_OT_AddHiders(bpy.types.Operator, HidersHandler):
    bl_idname = "daz.add_hide_drivers"
    bl_label = "Add Visibility Drivers"
    bl_description = "Control visibility with rig property. For file linking."
    bl_options = {'UNDO'}
    
    flag = "DazVisibilityDrivers"
    value = True

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and not ob.DazVisibilityDrivers)


    def handleProp(self, prop, clo, rig, context):
        from .driver import setBoolProp, makePropDriver
        if context.scene.DazHideOnlyMasked:
            masked = False
            for ob in rig.children:
                if ob.type == 'MESH':
                    for mod in ob.modifiers:
                        if (mod.type == 'MASK' and 
                            mod.name == getMaskName(clo.name)):
                            masked = True
                            break
            if not masked:
                return
        setBoolProp(rig, prop, True, "Show %s" % clo.name)
        makePropDriver(prop, clo, HideViewport, rig, expr="not(x)")
        makePropDriver(prop, clo, "hide_render", rig, expr="not(x)")

    
    def handleMod(self, prop, rig, mod):
        from .driver import makePropDriver
        makePropDriver(prop, mod, "show_viewport", rig, expr="x")
        makePropDriver(prop, mod, "show_render", rig, expr="x")


class DAZ_OT_RemoveHiders(bpy.types.Operator, HidersHandler):
    bl_idname = "daz.remove_hide_drivers"
    bl_label = "Remove Visibility Drivers"
    bl_description = "Remove ability to control visibility from rig property"
    bl_options = {'UNDO'}

    flag = "DazVisibilityDrivers"
    value = False

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'ARMATURE' and ob.DazVisibilityDrivers)

    def handleProp(self, prop, clo, rig, context):
        if prop in rig.keys():
            del rig[prop]
        clo.driver_remove(HideViewport)
        clo.driver_remove("hide_render")

    def handleMod(self, prop, rig, mod):
        mod.driver_remove("show_viewport")
        mod.driver_remove("show_render")

#------------------------------------------------------------------------
#   Hider collections
#------------------------------------------------------------------------

if bpy.app.version >= (2,80,0):
    
    class DAZ_OT_AddHiderCollections(bpy.types.Operator, HidersHandler):
        bl_idname = "daz.add_hide_collections"
        bl_label = "Add Visibility Collections"
        bl_description = "Control visibility with rig property. For file linking."
        bl_options = {'UNDO'}
        
        flag = "DazVisibilityCollections"
        value = True
    
        @classmethod
        def poll(self, context):
            ob = context.object
            return (ob and ob.type == 'ARMATURE' and not ob.DazVisibilityCollections)

        def getMeshesInGroup(self, context, rig):
            meshes = HidersHandler.getMeshesInGroup(self, context, rig)
            return [rig] + meshes
        
        def handleProp(self, prop, clo, rig, context):
            if self.collection is None:
                return
            subcoll = bpy.data.collections.new(clo.name)
            self.collection.children.link(subcoll)
            if clo in self.collection.objects.values():
                self.collection.objects.unlink(clo)
            subcoll.objects.link(clo)
        
        def handleMod(self, prop, rig, mod):
            return
    
    
    class DAZ_OT_RemoveHiderCollections(bpy.types.Operator, HidersHandler):
        bl_idname = "daz.remove_hide_collections"
        bl_label = "Remove Visibility Collections"
        bl_description = "Remove ability to control visibility from rig property"
        bl_options = {'UNDO'}
    
        flag = "DazVisibilityCollections"
        value = False
    
        @classmethod
        def poll(self, context):
            ob = context.object
            return (ob and ob.type == 'ARMATURE' and ob.DazVisibilityCollections)
    
        def getMeshesInGroup(self, context, rig):
            meshes = HidersHandler.getMeshesInGroup(self, context, rig)
            return [rig] + meshes
        
        def handleProp(self, prop, clo, rig, context):
            if self.collection is None:
                return
            for subcoll in self.collection.children.values():
                if clo in subcoll.objects.values():
                    if subcoll in self.collection.children.values():
                        self.collection.children.unlink(subcoll)
                    subcoll.objects.unlink(clo)
                    self.collection.objects.link(clo)
                    break
    
        def handleMod(self, prop, rig, mod):
            return

#------------------------------------------------------------------------
#   Show/Hide all
#------------------------------------------------------------------------

def setAllVisibility(context, prefix, value):
    from .morphing import autoKeyProp
    rig = context.object
    scn = context.scene
    if rig is None:
        return
    for key in rig.keys():
        if key[0:3] == prefix:
            if key:
                rig[key] = value
                autoKeyProp(rig, key, scn, scn.frame_current, True)
    updateScene(context)


class DAZ_OT_ShowAll(bpy.types.Operator, PrefixString):
    bl_idname = "daz.show_all"
    bl_label = "Show All"
    bl_description = "Show all meshes/makeup of this rig"
    bl_options = {'UNDO'}

    def execute(self, context):
        scn = context.scene
        setAllVisibility(context, self.prefix, True)
        return{'FINISHED'}


class DAZ_OT_HideAll(bpy.types.Operator, PrefixString):
    bl_idname = "daz.hide_all"
    bl_label = "Hide All"
    bl_description = "Hide all meshes/makeup of this rig"
    bl_options = {'UNDO'}

    def execute(self, context):
        scn = context.scene
        setAllVisibility(context, self.prefix, False)
        return{'FINISHED'}

#------------------------------------------------------------------------
#   Mask modifiers
#------------------------------------------------------------------------

def createMaskModifiers(context, useSelectedOnly):
    from .proxy import getSelectedObjects
    selected,_ = getSelectedObjects(context, 'MESH')
    ob = context.object
    scn = context.scene
    rig = ob.parent
    print("Create masks for %s:" % ob.name)
    if rig:
        for child in rig.children:
            if child.type == 'ARMATURE' and child.children:
                mesh = child.children[0]
            elif child.type == 'MESH':
                mesh = child
            else:
                mesh = None
            if mesh and mesh != ob:
                if useSelectedOnly and mesh not in selected:
                    continue
                mod = None
                for mod1 in ob.modifiers:
                    modname = getMaskName(mesh.name)
                    if mod1.type == 'MASK' and mod1.name == modname:
                        mod = mod1
                if modname in ob.vertex_groups.keys():
                    vgrp = ob.vertex_groups[modname]
                else:
                    vgrp = ob.vertex_groups.new(name=modname)
                print("  ", mesh.name)
                if mod is None:
                    mod = ob.modifiers.new(modname, 'MASK')
                mod.vertex_group = modname
                mod.invert_vertex_group = True
    print("Masks created")


class DAZ_OT_CreateMasks(bpy.types.Operator):
    bl_idname = "daz.create_all_masks"
    bl_label = "Create All Masks"
    bl_description = "Create vertex groups and mask modifiers in active mesh for all meshes belonging to same character"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

    def execute(self, context):
        try:
            createMaskModifiers(context, False)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}


class DAZ_OT_CreateSelectedMasks(bpy.types.Operator):
    bl_idname = "daz.create_selected_masks"
    bl_label = "Create Selected Masks"
    bl_description = "Create vertex groups and mask modifiers in active mesh for selected meshes"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

    def execute(self, context):
        try:
            createMaskModifiers(context, True)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}

#----------------------------------------------------------
#   Create collections
#----------------------------------------------------------

class DAZ_OT_CreateCollections(bpy.types.Operator):
    bl_idname = "daz.create_collections"
    bl_label = "Create Collections"
    bl_description = "Create collections for each empty in scene"
    bl_options = {'UNDO'}

    def execute(self, context):
        try:
            coll = context.collection
            for ob in list(coll.objects):
                if ob.type == 'EMPTY':
                    subcoll = bpy.data.collections.new(ob.name)
                    coll.children.link(subcoll)
                    coll.objects.unlink(ob)
                    subcoll.objects.link(ob)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}
        
#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_AddHiders,
    DAZ_OT_RemoveHiders,
    DAZ_OT_ShowAll,
    DAZ_OT_HideAll,
    DAZ_OT_CreateMasks,
    DAZ_OT_CreateSelectedMasks,
]

if bpy.app.version >= (2,80,0):
    classes += [
        DAZ_OT_AddHiderCollections,
        DAZ_OT_RemoveHiderCollections,
        DAZ_OT_CreateCollections,
    ]

def initialize():
    bpy.types.Object.DazVisibilityDrivers = BoolProperty(default = False)
    bpy.types.Object.DazVisibilityCollections = BoolProperty(default = False)

    bpy.types.Scene.DazHideOnlyMasked = BoolProperty(
        name = "Hide Only Masked",
        description = "Create visibility drivers only for masked meshes",
        default = False)

    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)


