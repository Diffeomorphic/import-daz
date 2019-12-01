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
from mathutils import Vector, Quaternion, Matrix
from .error import *
from .utils import *
from .settings import theSettings

if bpy.app.version < (2,80,0):
    from .buttons27 import JsonFile, MultiFile
else:
    from .buttons28 import JsonFile, MultiFile

#------------------------------------------------------------------
#   JSON fitting
#------------------------------------------------------------------

def loadJsonVerts(filepath):
    from .load_json import loadJson
    objects = {}
    rigs = {}
    struct = loadJson(filepath)
    if ("application" not in struct.keys() or
        struct["application"] != "export_basic_data"):
        msg = ("The file\n" +
               filepath + "           \n" +
               "does not contain basic data")
        raise DazError(msg)

    for figure in struct["figures"]:
        if "num verts" in figure.keys() and figure["num verts"] == 0:
            continue
        name = figure["name"]
        if name not in objects.keys():
            objects[name] = []

        if "vertices" in figure.keys():
            verts = [d2b(vec) for vec in figure["vertices"]]
            objects[name].append(verts)

        if "bones" not in figure.keys():
            continue

        locations = {}
        transforms = {}
        if name not in rigs.keys():
            rigs[name] = []
        rigs[name].append((locations, transforms))
        for bone in figure["bones"]:
            head = Vector(bone["center_point"])
            tail = Vector(bone["end_point"])
            vec = tail - head
            if "ws_transform" in bone.keys():
                ws = bone["ws_transform"]
                rmat = Matrix([ws[0:3], ws[3:6], ws[6:9]])
                head = Vector(ws[9:12])
                tail = head + Mult2(vec, rmat)
            else:
                head = Vector(bone["ws_pos"])
                x,y,z,w = bone["ws_rot"]
                quat = Quaternion((w,x,y,z))
                rmat = quat.to_matrix().to_3x3()
                ws = bone["ws_scale"]
                smat = Matrix([ws[0:3], ws[3:6], ws[6:9]])
                tail = head + Mult3(vec, smat, rmat)
                rmat = Mult2(smat, rmat)
            locations[bone["name"]] = (head, tail)
            rmat = rmat.to_4x4()
            rmat.col[3][0:3] = theSettings.scale*head
            transforms[bone["name"]] = (rmat, head, rmat.to_euler(), (1,1,1))

    return objects,rigs

#------------------------------------------------------------------
#
#------------------------------------------------------------------

def getFitFile(filepath):
    objpath = os.path.splitext(filepath)[0] + theSettings.fitFile
    if not os.path.exists(objpath):
        msg = ("Mesh fitting set to %s.\n" % theSettings.fitFile +
               "Export \"%s\"            \n" % objpath +
               "from Daz Studio to fit to %s file.\n" % theSettings.fitFile +
               "See documentation for more information.")
        raise DazError(msg)
    return objpath


def fitToFile(filepath, nodes):
    from .geometry import Geometry
    from .figure import FigureInstance
    from .bone import BoneInstance
    from .node import Instance

    print("Fitting objects with %s file..." % theSettings.fitFile)
    objpath = getFitFile(filepath)
    if theSettings.fitFile == ".json":
        objects,rigs = loadJsonVerts(objpath)
        subsurfaced = False
    else:
        print("fitToFile", ext)
        halt

    taken = dict([(name,0) for name in objects.keys()])
    takenfigs = dict([(name,[]) for name in rigs.keys()])
    unfitted = []
    for node,inst in nodes:
        if inst is None:
            print("fitToFile inst is None:\n  ", None)
            pass
        elif isinstance(inst, BoneInstance):
            inst.hasBoneParent = True
            continue
        elif (isinstance(inst.parent, Instance) and
                (inst.parent.hasBoneParent or
                 not isinstance(inst.parent, FigureInstance))):
            inst.hasBoneParent = True
            #if theSettings.verbosity > 1:
            #    print("  Dont fit %s" % inst.id)
            #continue
        else:
            pass

        if isinstance(inst, FigureInstance):
            if inst.node.name in rigs.keys():
                fitFigure(inst, rigs, takenfigs)

        for geonode in inst.geometries:
            geo = geonode.data
            if geo is None:
                continue
            nname = tryGetName(node.name, objects)
            if (nname is None and
                node.name[0].isdigit()):
                nname = tryGetName("a"+node.name, objects)

            if nname:
                idx = taken[nname]
                if idx >= len(objects[nname]):
                    msg = ("Too many instances of object %s: %d" % (nname, idx))
                    ok = False
                else:
                    verts = objects[nname][idx]
                    taken[nname] += 1
                    ok = True
                if not ok:
                    print(msg)
                    unfitted.append(node)
                elif subsurfaced:
                    if len(verts) < len(geo.verts):
                        msg = ("Mismatch %s, %s: %d < %d" % (node.name, geo.name, len(verts), len(geo.verts)))
                        print(msg)
                    else:
                        geonode.verts = verts[0:len(geo.verts)]
                else:
                    if len(verts) != len(geo.verts):
                        ok = False
                        for verts1 in getAlternatives(nname, objects):
                            if len(verts1) == len(geo.verts):
                                geonode.verts = verts1
                                ok = True
                                break
                        if not ok:
                            msg = ("Mismatch %s, %s: %d != %d" % (node.name, geo.name, len(verts), len(geo.verts)))
                            print(msg)
                    else:
                        geonode.verts = verts
            elif len(geo.verts) == 0:
                print("Zero verts:", node.name)
                pass
            else:
                unfitted.append(node)

    if unfitted:
        print("The following nodes were not found")
        print("and must be fitted manually:")
        for node in unfitted:
            print('    "%s"' % node.name)
        print("The following nodes were fitted:")
        for oname in objects.keys():
            print('    "%s"' % oname)


def fitFigure(inst, rigs, takenfigs):
    from .figure import FigureInstance
    from .bone import BoneInstance
    name = inst.node.name
    if name in rigs.keys():
        inst.clearTransforms()
        if inst.id in takenfigs[name]:
            return
        elif inst.index < len(rigs[name]):
            locations,transforms = rigs[name][inst.index]
            takenfigs[name].append(inst.id)
        else:
            print("Cannot fit %s" % name)
            return
    else:
        print("No fitting info for figure %s" % name)
        for key in rigs.keys():
            print("  ", key)
        return

    for child in inst.children.values():
        if isinstance(child, FigureInstance):
            fitFigure(child, rigs, takenfigs)
        elif isinstance(child, BoneInstance):
            fitBone(child, locations, transforms, rigs, takenfigs)


def fitBone(inst, locations, transforms, rigs, takenfigs):
    from .figure import FigureInstance
    from .bone import BoneInstance
    if inst.node.name not in locations.keys():
        return
    head,tail = locations[inst.node.name]
    inst.previewAttrs["center_point"] = head
    inst.previewAttrs["end_point"] = tail
    inst.clearTransforms()
    rmat,wsloc,wsrot,wsscale = transforms[inst.node.name]
    inst.restMatrix = rmat

    for child in inst.children.values():
        if isinstance(child, FigureInstance):
            fitFigure(child, rigs, takenfigs)
        if isinstance(child, BoneInstance):
            fitBone(child, locations, transforms, rigs, takenfigs)


def tryGetName(name, objects):
    replacements = [
        (" ", "_"),
        (" ", "-"),
        (".", "_"),
        (".", "-"),
    ]
    if name in objects.keys():
        return name
    else:
        name = name.replace("(","_").replace(")","_")
        for old,new in replacements:
            if name.replace(old, new) in objects.keys():
                return name.replace(old, new)
    return None


def getAlternatives(nname, objects):
    alts = []
    for oname,verts in objects.items():
        if nname == oname[:-2]:
            alts.append(verts)
    return alts


def fitToMesh(context):
    from .node import clearParent
    trg = context.object
    src = None
    for ob in getSceneObjects(context):
        if getSelected(ob) and ob != trg and ob.type == 'MESH':
            src = ob
            break
    if src is None:
        raise DazError("Two meshes must be selected")
    ns = len(src.data.vertices)
    nt = len(trg.data.vertices)
    if ns == nt:
        pass
    elif ns == 4*nt:
        print("Subsurfaced mesh:\n %d == 4*%d" % (ns, nt))
    else:
        raise DazError("Vertex number mismatch:\n %d != %d" % (ns, nt))

    activateObject(context, src)
    clearParent(src)
    for mod in src.modifiers:
        if mod.type == 'ARMATURE':
            bpy.ops.object.modifier_remove(modifier=mod.name)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    activateObject(context, trg)

    for v in trg.data.vertices:
        v.co = src.data.vertices[v.index].co


class DAZ_OT_FitToObject(bpy.types.Operator):
    bl_idname = "daz.fit_mesh_to_other"
    bl_label = "Fit Mesh To Other"
    bl_description = "Fit current mesh to selected mesh"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

    def execute(self, context):
        try:
            fitToMesh(context)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

class DAZ_OT_ImportJson(bpy.types.Operator, JsonFile, MultiFile):
    bl_idname = "daz.import_json"
    bl_label = "Import JSON Morph(s)"
    bl_description = "Import JSON file(s) (*.json) as morphs"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')


    def execute(self, context):
        try:
            self.buildMorphs(context)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}


    def buildMorphs(self, context):
        from .fileutils import getMultiFiles
        objects = [ob for ob in getSceneObjects(context)
                   if getSelected(ob) and ob.type == 'MESH']
        if not objects:
            return
        theSettings.scale = objects[0].DazScale
        paths = getMultiFiles(self, ["json"])
        for path in paths:
            for ob in objects:
                self.buildMorph(ob, path)


    def buildMorph(self, ob, filepath):
        objects,rigs = loadJsonVerts(filepath)
        if not ob.data.shape_keys:
            basic = ob.shape_key_add(name="Basic")
        else:
            basic = ob.data.shape_keys.key_blocks[0]
        sname = os.path.basename(os.path.splitext(filepath)[0])
        if sname in ob.data.shape_keys.key_blocks.keys():
            skey = ob.data.shape_keys.key_blocks[sname]
            ob.shape_key_remove(skey)
        skey = ob.shape_key_add(name=sname)
        for name,vlist in objects.items():
            verts = vlist[0]
            if len(verts) == len(ob.data.vertices):
                for vn,co in enumerate(verts):
                    skey.data[vn].co = co
                print("Morph %s created" % sname)
                return
        print("No matching morph found")

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_FitToObject,
    DAZ_OT_ImportJson,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
