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
import bpy
from bpy.props import *
from .error import *
if bpy.app.version < (2,80,0):
    from .buttons27 import DazImageFile, SingleFile, DazOptions, DazPropGroup, DazFormula, DazStringGroup
else:
    from .buttons28 import DazImageFile, SingleFile, DazOptions, DazPropGroup, DazFormula, DazStringGroup

#------------------------------------------------------------------
#   Import DAZ
#------------------------------------------------------------------

class ImportDAZ(bpy.types.Operator, DazImageFile, SingleFile, DazOptions):
    """Import a DAZ DUF/DSF File"""
    bl_idname = "daz.import_daz"
    bl_label = "Import DAZ File"
    bl_description = "Import a native DAZ file (*.duf, *.dsf, *.dse)"
    bl_options = {'PRESET', 'UNDO'}

    def execute(self, context):
        from .main import getMainAsset
        try:
            getMainAsset(self.filepath, context, self)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}


    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


    def draw(self, context):
        layout = self.layout
        scn = context.scene
        layout.prop(self, "unitScale")
        layout.separator()

        box = layout.box()
        box.label(text = "Mesh Fitting")
        box.prop(self, "fitMeshes", expand=True)

        layout.separator()
        layout.prop(self, "skinColor")
        layout.prop(self, "clothesColor")

#-------------------------------------------------------------
#   Property groups, for drivers
#-------------------------------------------------------------

def evalMorphs(pb, idx, key):
    rig = pb.constraints[0].target
    props = pb.DazLocProps if key == "Loc" else pb.DazRotProps if key == "Rot" else pb.DazScaleProps
    return sum([pg.factor*(rig[pg.prop]-pg.default) for pg in props if pg.index == idx])


def addCustomDriver(fcu, rig, pb, init, value, prop, key, errors, default=0.0):
    from .driver import addTransformVar, driverHasVar
    fcu.driver.type = 'SCRIPTED'
    if abs(value) > 1e-4:
        expr = 'evalMorphs(self, %d, "%s")' % (fcu.array_index, key)
        drvexpr = fcu.driver.expression[len(init):]
        if drvexpr in ["0.000", "-0.000"]:
            if init:
                fcu.driver.expression = init + "+" + expr
            else:
                fcu.driver.expression = expr
        elif expr not in drvexpr:
            if init:
                fcu.driver.expression = init + "(" + drvexpr + "+" + expr + ")"
            else:
                fcu.driver.expression = drvexpr + "+" + expr
        fcu.driver.use_self = True
        addSelfRef(rig, pb)
        addPropGroup(rig, pb, fcu.array_index, key, prop, value, default)
        if len(fcu.modifiers) > 0:
            fmod = fcu.modifiers[0]
            fcu.modifiers.remove(fmod)


def addSelfRef(rig, pb):
    if pb.constraints:
        cns = pb.constraints[0]
        if cns.name == "Do Not Touch":
            return
        else:
            raise(DazError, "Inconsistent self reference constraint")
    cns = pb.constraints.new('COPY_LOCATION')
    cns.name = "Do Not Touch"
    cns.target = rig
    cns.mute = True


def hasSelfRef(pb):
    return (pb.constraints and
            pb.constraints[0].name == "Do Not Touch")


def addPropGroup(rig, pb, idx, key, prop, value, default=0.0):
    props = pb.DazLocProps if key == "Loc" else pb.DazRotProps if key == "Rot" else pb.DazScaleProps
    clearProp(props, prop, idx)
    pg = props.add()
    pg.index = idx
    pg.prop = prop
    pg.factor = value
    pg.default = default


def removeFromPropGroup(props, prop):
    n = len(props)
    for idx in range(4):
        clearProp(props, prop, idx)


def clearProp(props, prop, idx):
    for n,pg in enumerate(props):
        if pg.prop == prop and pg.index == idx:
            props.remove(n)
            return


def getNewItem(collProp, key):
    for item in collProp:
        if item.key == key:
            return item
    item = collProp.add()
    item.key = key
    return item


def copyPropGroups(rig1, rig2, pb2):
    if pb2.name not in rig1.pose.bones.keys():
        return
    pb1 = rig1.pose.bones[pb2.name]
    if not (pb1.DazLocProps or pb1.DazRotProps or pb1.DazScaleProps):
        return
    addSelfRef(rig2, pb2)
    for props1,props2 in [
        (pb1.DazLocProps, pb2.DazLocProps),
        (pb1.DazRotProps, pb2.DazRotProps),
        (pb1.DazScaleProps, pb2.DazScaleProps)
        ]:
        for pg1 in props1:
            pg2 = props2.add()
            pg2.index = pg1.index
            pg2.prop = pg1.prop
            pg2.factor = pg1.factor
            pg2.default = pg1.default


def getPropGroupProps(rig):
    struct = {}
    for pb in rig.pose.bones:
        for props in [pb.DazLocProps, pb.DazRotProps, pb.DazScaleProps]:
            for pg in props:
                struct[pg.prop] = True
    return list(struct.keys())


def showPropGroups(rig):
    for pb in rig.pose.bones:
        if pb.bone.select:
            print("\n", pb.name)
            for key,props in [("Loc",pb.DazLocProps),
                              ("Rot",pb.DazRotProps),
                              ("Sca",pb.DazScaleProps)
                              ]:
                print("  ", key)
                for pg in props:
                    print("    ", pg.index, pg.prop, pg.factor, pg.default)


class DAZ_OT_ShowPropGroupsColor(bpy.types.Operator):
    bl_idname = "daz.show_prop_groups"
    bl_label = "Show Prop Groups"
    bl_description = "Show the property groups for the selected posebones."

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'ARMATURE')

    def execute(self, context):
        showPropGroups(context.object)
        return{'FINISHED'}

#-------------------------------------------------------------
#   Initialize
#-------------------------------------------------------------

from bpy.app.handlers import persistent

@persistent
def updateHandler(scn):
    global evalMorphs
    bpy.app.driver_namespace["evalMorphs"] = evalMorphs


classes = [
    ImportDAZ,
    DazPropGroup,
    DazFormula,
    DazStringGroup,
    DAZ_OT_ShowPropGroupsColor,
]

def initialize():

    #bpy.types.Scene.DazUnitScale = FloatProperty(
    #    name = "Unit Scale",
    #    description = "Scale used to convert between DAZ and Blender units (cm vs dm).",
    #    default = 0.1,
    #    precision = 3,
    #    min = 0.001, max = 10.0)

    bpy.types.Scene.DazAutoMaterials = BoolProperty(
        name = "Auto Material Method",
        description = "Use best shaders for material, independent of the settings below",
        default = True)

    if bpy.app.version < (2,80,0):
        default = 'PRINCIPLED'
    else:
        default = 'EEVEE'

    bpy.types.Scene.DazHandleOpaque = EnumProperty(
        items = [('BSDF', "BSDF", "Node setup with BSDF nodes"),
                 ('PRINCIPLED', "Principled", "Node setup with principled node"),
                 ('EEVEE', "Eevee", "Simple opaque material that works with Eevee"),
                 ],
        name = "Opaque Materials",
        description = "Default method used for opaque materials.\nIgnored by some materials.",
        default = default)

    if bpy.app.version < (2,80,0):
        default = 'GUESS'
    else:
        default = 'EEVEE'

    bpy.types.Scene.DazHandleRefractive = EnumProperty(
        items = [('BSDF', "BSDF", "Node setup with BSDF nodes"),
                 ('PRINCIPLED', "Principled", "Node setup with principled node"),
                 ('GUESS', "Guess", "Guess material properties, suitable for eyes. Turn on caustics."),
                 ('EEVEE', "Eevee", "Simple transparent material that works with Eevee"),
                 #('CUSTOM', "Custom Shader", "Use custom glass shader"),
                 #('COMPLEX', "Custom Shader (Unstable)", "Use custom glass shader in development"),
                 ],
        name = "Refractive Materials",
        description = "Default method used for refractive materials.\nIgnored by some materials.",
        default = default)

    bpy.types.Scene.DazUseEnvironment = BoolProperty(
        name = "Environment",
        description = "Load environment",
        default = True)

    bpy.types.Scene.DazChooseColors = EnumProperty(
        items = [('WHITE', "White", "Default diffuse color"),
                 ('RANDOM', "Random", "Random colors for each object"),
                 ('GUESS', "Guess", "Guess colors based on name"),
                 ],
        name = "Color Choice",
        description = "Method to use object colors",
        default = 'GUESS')

    bpy.types.Scene.DazUseHidden = BoolProperty(
        name = "Hidden Features",
        description = "Use hidden and undocumented experimental features",
        default = False)

    bpy.types.Scene.DazUseLockRot = BoolProperty(
        name = "Rotation Locks",
        description = "Use rotation locks",
        default = True)

    bpy.types.Scene.DazUseLockLoc = BoolProperty(
        name = "Location Locks",
        description = "Use location locks",
        default = True)

    bpy.types.Scene.DazUseLimitRot = BoolProperty(
        name = "Limit Rotation",
        description = "Create Limit Rotation constraints",
        default = False)

    bpy.types.Scene.DazUseLimitLoc = BoolProperty(
        name = "Limit Location",
        description = "Create Limit Location constraints",
        default = False)

    bpy.types.Scene.DazZup = BoolProperty(
        name = "Z Up",
        description = "Convert from DAZ's Y up convention to Blender's Z up convention",
        default = True)

    bpy.types.Scene.DazOrientation = BoolProperty(
        name = "DAZ Orientation",
        description = "Treat bones as nodes with same orientation as in Daz Studio",
        default = False)

    bpy.types.Scene.DazBestOrientation = BoolProperty(
        name = "DAZ Best Orientation",
        description = "Treat bones as nodes with same orientation as in Daz Studio,\nbut flip axes to make Y point along bone as well as possible.",
        default = False)

    from sys import platform
    bpy.types.Scene.DazCaseSensitivePaths = BoolProperty(
        name = "Case-Sensitive Paths",
        description = "Convert URLs to lowercase. Works best on Windows.",
        default = (platform != 'win32'))

    bpy.types.Scene.DazRename = BoolProperty(
        name = "Rename",
        description = "Rename all imported objects based on file name",
        default = False)

    bpy.types.Scene.DazUseGroup = BoolProperty(
        name = "Create Group",
        description = "Add all objects to the same group",
        default = True)

    bpy.types.Scene.DazUseConnect = BoolProperty(
        name = "Connect Bones",
        description = "Connect bones to parent if head coincides with parent tail.",
        default = True)

    bpy.types.Scene.DazAddFaceDrivers = BoolProperty(
        name = "Add Face Drivers",
        description = "Add drivers to facial morphs. Only for Genesis 1 and 2.",
        default = True)

    bpy.types.Scene.DazMakeDrivers = EnumProperty(
        items = [('NONE', "None", "Never make drivers"),
                 ('PROPS', "Props", "Make drivers for props"),
                 ('PEOPLE', "People", "Make drivers for people"),
                 ('ALL', "All", "Make drivers for all figures"),
                 ],
        name = "Make Drivers",
        description = "Make drivers for formulas",
        default = 'PROPS')

    bpy.types.Scene.DazMergeShells = BoolProperty(
        name = "Merge Shells",
        description = "Merge shell materials with object material",
        default = True)

    bpy.types.Scene.DazMaxBump = FloatProperty(
        name = "Max Bump Strength",
        description = "Max bump strength",
        default = 2.0,
        min = 0.1, max = 10)

    bpy.types.Scene.DazUseDisplacement = BoolProperty(
        name = "Displacement",
        description = "Use displacement maps. Affects internal renderer only",
        default = True)

    bpy.types.Object.DazUseDisplacement = BoolProperty(default=True)
    bpy.types.Material.DazUseDisplacement = BoolProperty(default=False)

    bpy.types.Scene.DazUseTranslucency = BoolProperty(
        name = "Translucency",
        description = "Use translucency.",
        default = True)

    bpy.types.Object.DazUseTranslucency = BoolProperty(default=True)
    bpy.types.Material.DazUseTranslucency = BoolProperty(default=False)

    bpy.types.Scene.DazUseSSS = BoolProperty(
        name = "SSS",
        description = "Use subsurface scattering.",
        default = True)

    bpy.types.Object.DazUseSSS = BoolProperty(default=True)
    bpy.types.Material.DazUseSSS = BoolProperty(default=False)

    bpy.types.Scene.DazUseTextures = BoolProperty(
        name = "Textures",
        description = "Use textures in all channels.",
        default = True)

    bpy.types.Object.DazUseTextures = BoolProperty(default=True)
    bpy.types.Material.DazUseTextures = BoolProperty(default=False)

    bpy.types.Scene.DazUseNormal = BoolProperty(
        name = "Normal",
        description = "Use normal maps.",
        default = True)

    bpy.types.Object.DazUseNormal = BoolProperty(default=True)
    bpy.types.Material.DazUseNormal = BoolProperty(default=False)

    bpy.types.Scene.DazUseBump = BoolProperty(
        name = "Bump",
        description = "Use bump maps.",
        default = True)

    bpy.types.Object.DazUseBump = BoolProperty(default=True)
    bpy.types.Material.DazUseBump = BoolProperty(default=False)

    bpy.types.Scene.DazUseEmission = BoolProperty(
        name = "Emission",
        description = "Use emission.",
        default = True)

    bpy.types.Scene.DazUseReflection = BoolProperty(
        name = "Reflection",
        description = "Use reflection maps. Affects internal renderer only",
        default = True)

    bpy.types.Scene.DazDiffuseRoughness = FloatProperty(
        name = "Diffuse Roughness",
        description = "Default diffuse roughness",
        default = 0.3,
        min = 0, max = 1.0)

    bpy.types.Scene.DazSpecularRoughness = FloatProperty(
        name = "Specular Roughness",
        description = "Default specular roughness",
        default = 0.3,
        min = 0, max = 1.0)

    bpy.types.Scene.DazDiffuseShader = EnumProperty(
        items = [
            ('FRESNEL', "Fresnel", ""),
            ('MINNAERT', "Minnaert", ""),
            ('TOON', "Toon", ""),
            ('OREN_NAYAR', "Oren-Nayar", ""),
            ('LAMBERT', "Lambert", "")
        ],
        name = "Diffuse Shader",
        description = "Diffuse shader (Blender Internal)",
        default = 'OREN_NAYAR')

    bpy.types.Scene.DazSpecularShader = EnumProperty(
        items = [
            ('WARDISO', "WardIso", ""),
            ('TOON', "Toon", ""),
            ('BLINN', "Blinn", ""),
            ('PHONG', "Phong", ""),
            ('COOKTORR', "CookTorr", "")
        ],
        name = "Specular Shader",
        description = "Specular shader (Blender Internal)",
        default = 'BLINN')

    bpy.types.Material.DazRenderEngine = StringProperty(default='NONE')
    bpy.types.Material.DazShader = StringProperty(default='NONE')
    bpy.types.Material.DazThinGlass = BoolProperty(default=False)

    bpy.types.Object.DazUDimsCollapsed = BoolProperty(default=False)
    bpy.types.Material.DazUDimsCollapsed = BoolProperty(default=False)
    bpy.types.Material.DazUDim = IntProperty(default=0)
    bpy.types.Material.DazVDim = IntProperty(default=0)

    #bpy.types.Scene.DazDriverType = EnumProperty(
    #    items = [('DIRECT', "Direct", "Drive bones directly. Causes problems if many expressions are loaded."),
    #             ('HANDLER', "Handler", "Use handlers to drive bones. Unstable and slow."),
    #             ('FUNCTION', "Function", "Use driver functions to drive bones. Probably best."),
    #             ],
    #    name = "Driver Type",
    #    description = "How to construct expressions for scripted drivers.",
    #    default = 'FUNCTION')

    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.PoseBone.DazLocProps = CollectionProperty(type = DazPropGroup)
    bpy.types.PoseBone.DazRotProps = CollectionProperty(type = DazPropGroup)
    bpy.types.PoseBone.DazScaleProps = CollectionProperty(type = DazPropGroup)
    bpy.types.Object.DazFormulas = CollectionProperty(type = DazFormula)
    bpy.types.Object.DazHiddenProps = CollectionProperty(type = DazStringGroup)

    bpy.app.driver_namespace["evalMorphs"] = evalMorphs
    bpy.app.handlers.load_post.append(updateHandler)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
