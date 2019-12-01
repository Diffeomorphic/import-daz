# Copyright (c) 2016, Thomas Larsson
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
from .error import *
from .utils import *
if bpy.app.version < (2,80,0):
    from .buttons27 import DazImageFile, SingleFile, TransferOptions, MergeShapekeysOptions
else:
    from .buttons28 import DazImageFile, SingleFile, TransferOptions, MergeShapekeysOptions


class MorphTransferer(DazImageFile, SingleFile, TransferOptions):
    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.data.shape_keys)


    def draw(self, context):
        layout = self.layout
        layout.label(text = "Transfer Method:")
        layout.prop(self, "transferMethod", expand=True)
        if self.transferMethod != 'AUTO':
            layout.label(text = "File Search Method:")
            layout.prop(self, "searchMethod", expand=True)
        layout.prop(self, "useDriver")
        layout.prop(self, "useActiveOnly")
        layout.prop(self, "startsWith")
        layout.prop(self, "useSelectedOnly")
        layout.prop(self, "ignoreRigidity")


    def execute(self, context):
        try:
            self.transferAllMorphs(context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}


    def invoke(self, context, event):
        from .asset import setDazPaths
        from .fileutils import getFolder
        scn = context.scene
        clothes = self.getClothes(context.object, context)
        if len(clothes) > 0:
            folder = getFolder(clothes[0], scn, ["Morphs/", ""])
            if folder is not None:
                self.properties.filepath = folder
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


    def transferMorphs(self, hum, clo, context):
        from .driver import getShapekeyBoneDriver, getShapekeyPropDriver, copyDriver
        from .asset import setDazPaths

        print("Transfer morphs %s => %s" %(hum.name, clo.name))
        scn = context.scene
        setDazPaths(scn)
        setActiveObject(context, clo)
        if not clo.data.shape_keys:
            basic = clo.shape_key_add(name="Basic")
        else:
            basic = None
        hskeys = hum.data.shape_keys
        if hum.active_shape_key_index < 0:
            hum.active_shape_key_index = 0
        clo.active_shape_key_index = 0

        for hskey in hskeys.key_blocks[1:]:
            sname = hskey.name
            if self.useActiveOnly and hskey != hum.active_shape_key:
                continue
            if self.startsWith and sname[0:len(self.startsWith)] != self.startsWith:
                continue

            if hskey.name[0:2] == "Dz":
                if not self.useExpressions:
                    continue
            elif hskey.name[0:4].lower() == "pjcm":
                if not self.useCorrectives:
                    continue
            elif self.useExpressions or self.useCorrectives:
                continue

            if self.useDriver:
                if self.useBoneDriver:
                    fcu = getShapekeyBoneDriver(hskeys, sname)
                elif self.usePropDriver:
                    fcu = getShapekeyPropDriver(hskeys, sname)
                #if (fcu is None and
                #    (self.useCorrectives or self.useExpressions)):
                #    continue
            else:
                fcu = None

            if not self.useActiveOnly and self.ignoreMorph(hum, clo, hskey):
                print(" 0", sname)
                continue

            if sname in clo.data.shape_keys.key_blocks.keys():
                cskey = clo.data.shape_keys.key_blocks[sname]
                clo.shape_key_remove(cskey)

            cskey = None
            if self.transferMethod != 'AUTO':
                path = self.getMorphPath(sname, clo, scn)
                if path is not None:
                    from .morphing import LoadShapekey
                    from .settings import theSettings
                    loader = LoadShapekey(mesh=clo)
                    theSettings.forMorphLoad(clo, scn, False)
                    loader.errors = {}
                    loader.getSingleMorph(path, scn)
                    if sname in clo.data.shape_keys.key_blocks.keys():
                        cskey = clo.data.shape_keys.key_blocks[sname]

            if cskey:
                print(" *", sname)
            elif self.transferMethod != 'FILES':
                if self.autoTransfer(hum, clo, hskey):
                    cskey = clo.data.shape_keys.key_blocks[sname]
                    print(" +", sname)
                    if cskey and not self.ignoreRigidity:
                        correctForRigidity(clo, cskey)

            if cskey:
                cskey.slider_min = hskey.slider_min
                cskey.slider_max = hskey.slider_max
                cskey.value = hskey.value
                if fcu is not None:
                    copyDriver(fcu, cskey)
            else:
                print(" -", sname)

        if (basic and
            len(clo.data.shape_keys.key_blocks) == 1 and
            clo.data.shape_keys.key_blocks[0] == basic):
            print("No shapekeys transferred to %s" % clo.name)
            clo.shape_key_remove(basic)



    def autoTransfer(self, hum, clo, hskey):
        hverts = hum.data.vertices
        cverts = clo.data.vertices
        eps = 1e-4
        facs = {0:1.0, 1:1.0, 2:1.0}
        offsets = {0:0.0, 1:0.0, 2:0.0}
        for n,vgname in enumerate(["_trx", "_try", "_trz"]):
            coord = [data.co[n] - hverts[j].co[n] for j,data in enumerate(hskey.data)]
            if min(coord) == max(coord):
                fac = 1.0
            else:
                fac = 1.0/(max(coord)-min(coord))
            facs[n] = fac
            offs = offsets[n] = min(coord)
            weights = [fac*(co-offs) for co in coord]

            vgrp = hum.vertex_groups.new(name=vgname)
            for vn,w in enumerate(weights):
                vgrp.add([vn], w, 'REPLACE')

            mod = clo.modifiers.new(vgname, 'DATA_TRANSFER')
            for i in range(4):
                bpy.ops.object.modifier_move_up(modifier=mod.name)
            mod.object = hum
            mod.use_vert_data = True
            #'TOPOLOGY', 'NEAREST', 'EDGE_NEAREST', 'EDGEINTERP_NEAREST',
            # 'POLY_NEAREST', 'POLYINTERP_NEAREST', 'POLYINTERP_VNORPROJ'
            mod.vert_mapping = 'POLYINTERP_NEAREST'
            mod.data_types_verts = {'VGROUP_WEIGHTS'}
            mod.layers_vgroup_select_src = vgname
            mod.mix_mode = 'REPLACE'
            bpy.ops.object.datalayout_transfer(modifier=mod.name)
            bpy.ops.object.modifier_apply(apply_as='DATA', modifier=mod.name)
            hum.vertex_groups.remove(vgrp)

        coords = []
        isZero = True
        for n,vgname in enumerate(["_trx", "_try", "_trz"]):
            vgrp = clo.vertex_groups[vgname]
            weights = [[g.weight for g in v.groups if g.group == vgrp.index][0] for v in clo.data.vertices]
            fac = facs[n]
            offs = offsets[n]
            coord = [cverts[j].co[n] + w/fac + offs for j,w in enumerate(weights)]
            coords.append(coord)
            wmax = max(weights)/fac + offs
            wmin = min(weights)/fac + offs
            if abs(wmax) > eps or abs(wmin) > eps:
                isZero = False
            clo.vertex_groups.remove(vgrp)

        if isZero:
            return False

        cskey = clo.shape_key_add(name=hskey.name)
        if self.useSelectedOnly:
            verts = clo.data.vertices
            for n in range(3):
                for j,x in enumerate(coords[n]):
                    if verts[j].select:
                        cskey.data[j].co[n] = x
        else:
            for n in range(3):
                for j,x in enumerate(coords[n]):
                    cskey.data[j].co[n] = x

        return True


    def ignoreMorph(self, hum, clo, hskey):
        eps = 0.01 * hum.DazScale   # 0.1 mm
        hverts = [v.index for v in hum.data.vertices if (hskey.data[v.index].co - v.co).length > eps]
        for j in range(3):
            xclo = [v.co[j] for v in clo.data.vertices]
            xkey = [hskey.data[vn].co[j] for vn in hverts]
            if xclo and xkey:
                minclo = min(xclo)
                maxclo = max(xclo)
                minkey = min(xkey)
                maxkey = max(xkey)
                if minclo > maxkey or maxclo < minkey:
                    return True
        return False


    def getClothes(self, hum, context):
        objects = []
        for ob in getSceneObjects(context):
            if getSelected(ob) and ob != hum and ob.type == 'MESH':
                objects.append(ob)
        return objects


    def transferAllMorphs(self, context):
        import time
        t1 = time.clock()
        hum = context.object
        if not hum.data.shape_keys:
            raise DazError("Cannot transfer because object    \n%s has no shapekeys   " % (hum.name))
        for ob in self.getClothes(hum, context):
            self.transferMorphs(hum, ob, context)
        t2 = time.clock()
        print("Morphs transferred in %.1f seconds" % (t2-t1))


    def getMorphPath(self, sname, ob, scn):
        from .fileutils import getFolder
        file = sname + ".dsf"
        if (self.searchMethod == 'AUTO' or
            self.filepath is None):
            folder = getFolder(ob, scn, ["Morphs/"])
        else:
            folder = os.path.dirname(self.filepath)
            if not os.path.exists(folder):
                return None
            if self.searchMethod == 'CURRENT':
                if file in os.listdir(folder):
                    return os.path.join(folder, file)
                else:
                    return None
        if folder:
            return findFileRecursive(folder, file)
        else:
            return None


def findFileRecursive(folder, tfile):
    for file in os.listdir(folder):
        path = os.path.join(folder, file)
        if file == tfile:
            return path
        elif os.path.isdir(path):
            tpath = findFileRecursive(path, tfile)
            if tpath:
                return tpath
    return None


def correctForRigidity(ob, skey):
    from mathutils import Matrix

    if "Rigidity" in ob.vertex_groups.keys():
        idx = ob.vertex_groups["Rigidity"].index
        for v in ob.data.vertices:
            for g in v.groups:
                if g.group == idx:
                    x = skey.data[v.index]
                    x.co = v.co + (1 - g.weight)*(x.co - v.co)

    for rgroup in ob.data.DazRigidityGroups:
        rotmode = rgroup.rotation_mode
        scalemodes = rgroup.scale_modes.split(" ")
        maskverts = [elt.a for elt in rgroup.mask_vertices]
        refverts = [elt.a for elt in rgroup.reference_vertices]

        if rotmode != "none":
            raise RuntimeError("Not yet implemented: Rigidity rotmode = %s" % rotmode)

        xcoords = [ob.data.vertices[vn].co for vn in refverts]
        ycoords = [skey.data[vn].co for vn in refverts]
        xsum = Vector((0,0,0))
        ysum = Vector((0,0,0))
        for co in xcoords:
            xsum += co
        for co in ycoords:
            ysum += co
        xcenter = xsum/len(refverts)
        ycenter = ysum/len(refverts)

        xdim = ydim = 0
        for n in range(3):
            xs = [abs(co[n]-xcenter[n]) for co in xcoords]
            ys = [abs(co[n]-ycenter[n]) for co in ycoords]
            xdim += sum(xs)
            ydim += sum(ys)

        scale = ydim/xdim
        smat = Matrix.Identity(3)
        for n,smode in enumerate(scalemodes):
            if smode == "primary":
                smat[n][n] = scale

        for n,vn in enumerate(maskverts):
            skey.data[vn].co = Mult2(smat, (ob.data.vertices[vn].co - xcenter)) + ycenter


def findVertsInGroup(ob, vgrp):
    idx = vgrp.index
    verts = []
    for v in ob.data.vertices:
        for g in v.groups:
            if g.group == idx:
                verts.append(v.index)
    return verts


class DAZ_OT_TransferExpressions(bpy.types.Operator, MorphTransferer):
    bl_idname = "daz.transfer_expressions"
    bl_label = "Transfer Expressions"
    bl_description = "Transfer facial expressions shapekeys with drivers from active to selected"
    bl_options = {'UNDO'}

    useBoneDriver = False
    usePropDriver = True
    useExpressions = True
    useCorrectives = False
    useIgnore = False


class DAZ_OT_TransferShapekeys(bpy.types.Operator, MorphTransferer):
    bl_idname = "daz.transfer_other_shapekeys"
    bl_label = "Transfer Other Shapekeys"
    bl_description = "Transfer all shapekeys except correctives and facial expressions with drivers from active to selected"
    bl_options = {'UNDO'}

    useBoneDriver = False
    usePropDriver = True
    useExpressions = False
    useCorrectives = False
    useIgnore = False


class DAZ_OT_TransferCorrectives(bpy.types.Operator, MorphTransferer):
    bl_idname = "daz.transfer_correctives"
    bl_label = "Transfer Correctives"
    bl_description = "Transfer corrective shapekeys and drivers from active to selected"
    bl_options = {'UNDO'}

    useBoneDriver = True
    usePropDriver = False
    useExpressions = False
    useCorrectives = True
    useIgnore = True

#----------------------------------------------------------
#   Merge Shapekeys
#----------------------------------------------------------

class DAZ_OT_MergeShapekeys(bpy.types.Operator, MergeShapekeysOptions):
    bl_idname = "daz.merge_shapekeys"
    bl_label = "Merge Shapekeys"
    bl_description = "Merge shapekeys"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.data.shape_keys)


    def draw(self, context):
        self.layout.prop(self, "shape1")
        self.layout.prop(self, "shape2")


    def execute(self, context):
        try:
            self.merge(context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}


    def invoke(self, context, event):
        context.window_manager.invoke_props_dialog(self)
        return {'RUNNING_MODAL'}


    def merge(self, context):
        ob = context.object
        skeys = ob.data.shape_keys.key_blocks
        if self.shape1 == self.shape2:
            raise DazError("Cannot merge shapekey to itself")
        skey1 = skeys[self.shape1]
        skey2 = skeys[self.shape2]
        for n,v in enumerate(ob.data.vertices):
            skey1.data[n].co += skey2.data[n].co - v.co
        idx = skeys.keys().index(self.shape2)
        ob.active_shape_key_index = idx
        bpy.ops.object.shape_key_remove()

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_TransferExpressions,
    DAZ_OT_TransferShapekeys,
    DAZ_OT_TransferCorrectives,
    DAZ_OT_MergeShapekeys,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
