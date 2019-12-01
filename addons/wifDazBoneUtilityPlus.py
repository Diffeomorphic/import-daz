bl_info = {
    "name": "DAZ rig bone utility",
    "author": "WaitInFuture",
    "version": (1, 8, 1),
    "blender": (2, 80, 0),
    "location": "View3D > Npanel",
    "description": "renameDAZgenesisBone, adjust rig pos for daz importer rig",
    "warning": "testonly",
    "wiki_url": "https://bitbucket.org/engetudouiti/wifdazimportaddons/src/master/",
    "tracker_url": "",
    "category": "Rigging"}

import bpy
from mathutils import Vector, Matrix, Quaternion
from math import radians, pi
import json
import os

from ..utils import *
if bpy.app.version < (2,80,0):
    Region = "TOOLS"
    from .. import buttons27 as buttons
else:
    Region = "UI"
    from .. import buttons28 as buttons


class WIF_PT_dazBoneUtils(bpy.types.Panel):
    bl_label = "WIF DAZ bone utility"
    bl_space_type = "VIEW_3D"
    bl_region_type = Region
    bl_category = "DAZ BoneTool"

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=False)
        row.operator("bonename.change", text="Change Bone Name")
        row = layout.row(align=False)
        row.operator("bonename.dazname", text="Return Bone Name")
        row = layout.row(align=False)
        row.operator("import_js.dazdata", text="import json")
        row = layout.row(align=False)
        row.operator("dazbone.adjust", text="Adjust Daz bones")
        row = layout.row(align=False)
        row.operator("dazbone.flipbone", text="Flip selected edit bones")

class WIF_OT_changeDazBoneName(bpy.types.Operator):
    bl_idname = "bonename.change"
    bl_label = "text"
    bl_description = "change bones name for blender mirror"
    bl_options = {'UNDO'}

    def execute(self, context):
        pblist = bpy.context.object.pose.bones
        for pb in pblist:
            bName = pb.name
            if bName[0] == "r" and bName[1] != ".":
                lbname= "l" + bName[1:]
                for lpb in pblist:
                    lpbName = lpb.name
                    if lpbName == lbname:
                        lpbName = lpbName[:1] + "." + lpbName[1:]
                        lpb.name = lpbName
                        bName = bName[:1] + "." + bName[1:]
                        pb.name=bName
        return{'FINISHED'}

class WIF_OT_returnDazBoneName(bpy.types.Operator):
    bl_idname = "bonename.dazname"
    bl_label = "text"
    bl_description = "return bones names as default"
    bl_options = {'UNDO'}

    def execute(self, context):
        pblist = bpy.context.object.pose.bones
        for pb in pblist:
            bName = pb.name
            if bName[0] == "r" and bName[1] == ".":
                lbname= "l" + bName[1:]
                for lpb in pblist:
                    lpbName = lpb.name
                    if lpbName == lbname:
                        lpbName = lpbName[:1] + lpbName[2:]
                        lpb.name = lpbName
                        bName = bName[:1] + bName[2:]
                        pb.name=bName
        return{'FINISHED'}

def read_daz_json(context, fp):
    f = open(fp, 'r', encoding='utf-8')
    print(f.name)
    dazdata = json.load(f)
    return (dazdata)

def convert_daz_json(dazdata):

    if "figures" in dazdata.keys():
        figdic = dazdata["figures"]
    else:
        print("no figure in json")
        return

    figdata = {}
    for fig in figdic:
        if ("bones" in fig.keys() and
            "label" in fig.keys()):
            figdata[fig["label"]] = fig["bones"]

    amtdic = {}
    for key in figdata.keys(): #key=figure label, bones = figdata[key]
        bonedic = {}
        for bn in figdata[key]:
            bonedic[bn["name"]] = {"cp": bn["center_point"], "ep": bn["end_point"], "rot": bn["ws_rot"]}
        amtdic[key] = bonedic
    return amtdic

def set_daz_props(rigs, dazdata):
    amtdic = convert_daz_json(dazdata)
    for rig in rigs:
        setSelected(rig, False)
    for rig in rigs:
        if rig.type == 'ARMATURE' and "DazRig" in rig.keys():
            setSelected(rig, True)
            setActiveObject(bpy.context, rig)
            rig = bpy.context.active_object
            bpy.ops.object.mode_set(mode = 'EDIT')
            ebones = rig.data.edit_bones
            sname = rig.name

            rigflag = 0
            rigdic = {}
            for fname in amtdic.keys():
                if fname == sname:
                    rigflag = 1
                    rigdic = amtdic[fname]
                    print("find:", fname)
                    break

            for bn in ebones:
                wsrot = [0,0,0,1]
                wscp = bn["DazHead"]
                wsep = bn["DazTail"]
                flag = [0,0,0]
                for bname in rigdic.keys():
                    if bname == bn.name:
                        if "rot" in rigdic[bname].keys():
                            flag[0] = 1
                            wsrot = rigdic[bname]["rot"]
                        if "cp" in rigdic[bname].keys():
                            flag[1] = 1
                            wscp = rigdic[bname]["cp"]
                        if "ep" in rigdic[bname].keys():
                            flag[2] = 1
                            wsep = rigdic[bname]["ep"]
                        break
                if not flag == [1,1,1]:
                    print(bn.name,":", flag)
                    break

                bn["DazWsrot"] = wsrot
                bn["DazCp"] = wscp
                bn["DazEp"] = wsep

            print(rig.name, ":addprop for bones complete")
            bpy.ops.object.mode_set(mode = 'OBJECT')

class WIF_OP_ImportDazData(bpy.types.Operator, buttons.SingleFile, buttons.JsonFile):
    bl_idname = "import_js.dazdata"
    bl_label = "Import daz rig data"
    bl_options = {'UNDO'}

    def execute(self, context):
        dazdata = read_daz_json(context, self.filepath)
        rigs = bpy.context.selected_objects
        set_daz_props(rigs, dazdata)
        return{'FINISHED'}

def circulate_tp(tcp,tep,ro,length):
    roll = 0
    tp = Vector((0, 0, 0))

    if ro[0] == "X" :       #xyz xzy
        if tep[0] >= tcp[0]:
            tp[0] =  length
            if ro[1] == "Y" :
                roll = pi
            else:
                roll = -pi/2
        else:
            tp[0] =  -length
            if ro[1] == "Y" :
                roll = pi
            else:
                roll = pi/2

    elif ro[0] == "Y" :   #yxz, yzx
        if tep[1] >= tcp[1] :
            tp[2] = length
            if ro[1] == "X":
                roll = -pi/2
            else:
                roll = 0

        else:
            tp[2] = -length
            if ro[1] == "X":
                roll =  pi/2
            else:
                roll = 0

    else:
        if tep[2] >= tcp[2] :
            tp[1] = -length
            if ro[1] == "X":
                roll = -pi/2
            else:
                roll = -pi
        else:
            tp[1] =  length
            if ro[1] == "X":
                roll = -pi/2
            else:
                roll = 0

    return tp, roll

def orientate_bone(ebn, ot, pr):
    rx = radians(ot[0])
    ry = radians(ot[1])
    rz = -radians(ot[2])

    dq = [-pr[3], pr[0], -pr[2], pr[1]]
    dquat = Quaternion(dq)
    bp_mat = dquat.to_matrix()
    mat_pr = bp_mat.to_4x4()

    mat_o = ebn.matrix
    mat_ra = Matrix.Rotation(rx, 4, 'X')
    mat_rb = Matrix.Rotation(ry, 4, 'Z')
    mat_rc = Matrix.Rotation(rz, 4, 'Y')
    if bpy.app.version < (2,80,0):
        mat_r = mat_pr * mat_rc * mat_rb * mat_ra
        ebn.matrix = mat_r * mat_o
    else:
        mat_r = mat_pr @ mat_rc @ mat_rb @ mat_ra
        ebn.matrix = mat_r @ mat_o

def trans_bone(ebn, cp):
    tcp = Vector((cp[0], -cp[2], cp[1]))
    ebn.translate(tcp)

def generate_ds_bone(amt,cp,ep,tcp,tep,ro,ot,pr,name):

    length = abs((ep - cp).length)
    #print(length)
    bn = amt.data.edit_bones.new(name)
    bn.head = (0, 0, 0)
    tpr = circulate_tp(tcp,tep,ro,length)
    bn.tail = tpr[0]
    bn.roll = tpr[1]
    orientate_bone(bn, ot, pr)
    trans_bone(bn, cp)

    bn.layers[16] = True
    bn.layers[0] = False

def copy_edit_bone(amt, bname, name):
    ebones = amt.data.edit_bones
    ebones[bname].tail = ebones[name].tail
    ebones[bname].align_orientation(ebones[name])

    #activate below function to remove generate _edit bones
    ebones.remove(ebones[name])

class WIF_OT_adjustDazBonePos(bpy.types.Operator):
    bl_idname = "dazbone.adjust"
    bl_label = "text"
    bl_description = "adjust tip and local axis of selected daz rigs"
    bl_options = {'UNDO'}

    def execute(self, context):
        objs = bpy.context.selected_objects

        for ob in objs:
            setSelected(ob, False)
        for ob in objs:
            if ob.type == 'ARMATURE' and "DazRig" in ob.keys():
                setSelected(ob, True)
                setActiveObject(bpy.context, ob)
                amt = bpy.context.active_object
                print(amt.name)
                bpy.ops.object.mode_set(mode = 'EDIT')
                ebones = amt.data.edit_bones
                pbones = amt.pose.bones
                bn_lst = []
                for bn in ebones:
                    if "DazHead" in bn.keys() and "DazRotMode" in pbones[bn.name].keys():
                        bn_lst.append(bn.name)
                for bname in bn_lst:
                    if bname not in ebones.keys():
                        print("Missing bone: %s" % bname)
                        continue
                    if "DazCp" not in ebones[bname].keys():
                        print("Bone without DazCp: %s" % bname)
                        continue

                    name = bname + "_Edt"
                    cp = ebones[bname]["DazHead"]
                    ep = ebones[bname]["DazTail"]
                    ro = pbones[bname]["DazRotMode"]
                    ot = ebones[bname]["DazOrientation"]

                    dcp = ebones[bname]["DazCp"]
                    dep = ebones[bname]["DazEp"]

                    pr = ebones[bname]["DazWsrot"]
                    cp = Vector(cp)/100
                    dcp = Vector(dcp)/100
                    ep = Vector(ep)/100
                    dep = Vector(dep)/100

                    generate_ds_bone(amt,cp,ep,dcp,dep,ro,ot,pr,name)
                    copy_edit_bone(amt, bname, name)
                bpy.ops.object.mode_set(mode = 'OBJECT')
        return{'FINISHED'}

class WIF_OT_flipBones(bpy.types.Operator):
    bl_idname = "dazbone.flipbone"
    bl_label = "text"
    bl_description = "flip selected edit-bones along bone direciton"
    bl_options = {'UNDO'}

    def execute(self, context):
        ob = bpy.context.active_object
        slist = []
        if ob.type == "ARMATURE" and ob.mode == "EDIT":
            ebn = bpy.context.selected_bones
            for bn in ebn:
                slist.append(bn.name)
            print(slist)
            for bn in slist:
                ebone = ob.data.edit_bones[bn]
                ehead = ebone.head
                etail = ebone.tail
                ebone.tail = ehead + ehead - etail

        return{'FINISHED'}

classes = (
    WIF_PT_dazBoneUtils,
    WIF_OT_changeDazBoneName,
    WIF_OT_returnDazBoneName,
    WIF_OP_ImportDazData,
    WIF_OT_adjustDazBonePos,
    WIF_OT_flipBones
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()