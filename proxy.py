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
from mathutils import Vector
from .error import *
from .tables import *
from .utils import *
if bpy.app.version < (2,80,0):
    from .buttons27 import UseAllBool
else:
    from .buttons28 import UseAllBool


#-------------------------------------------------------------
#   Make proxy
#-------------------------------------------------------------


def makeProxy1(context, iterations):
    ob = context.object
    bpy.ops.object.duplicate()
    pxy = context.object
    makeRawProxy(pxy, iterations)
    pxy.name = stripName(ob.name) + ("_Lod%d" % iterations)
    if bpy.app.version < (2,80,0):
        pxy.layers = list(ob.layers)
    insertSeams(ob, pxy)
    print("Low-poly %s created" % pxy.name)
    return pxy


def stripName(string):
    if string[-5:] == "_Mesh":
        return string[:-5]
    elif (len(string) > 4 and
        string[-4] == "." and
        string[-3:].isdigit()):
        return string[:-4]
    else:
        return string


def makeRawProxy(pxy, iterations):
    mod = pxy.modifiers.new("Proxy", 'DECIMATE')
    mod.decimate_type = 'UNSUBDIV'
    mod.iterations = iterations
    bpy.ops.object.modifier_apply(apply_as='DATA', modifier=mod.name)


#-------------------------------------------------------------
#   Find polys
#-------------------------------------------------------------

def findHumanAndProxy(context):
    hum = pxy = None
    for ob in getSceneObjects(context):
        if ob.type == 'MESH':
            if hum is None:
                hum = ob
            else:
                pxy = ob
    if len(pxy.data.vertices) > len(hum.data.vertices):
        ob = pxy
        pxy = hum
        hum = ob
    return hum,pxy


def assocPxyHumVerts(hum, pxy):
    pxyHumVerts = {}
    hverts = [(hv.co, hv.index) for hv in hum.data.vertices]
    hverts.sort()
    pverts = [(pv.co, pv.index) for pv in pxy.data.vertices]
    pverts.sort()
    for pco,pvn in pverts:
        hco,hvn = hverts[0]
        while (pco-hco).length > 1e-4:
            hverts = hverts[1:]
            hco,hvn = hverts[0]
        pxyHumVerts[pvn] = hvn
    humPxyVerts = dict([(hvn,None) for hvn in range(len(hum.data.vertices))])
    for pvn,hvn in pxyHumVerts.items():
        humPxyVerts[hvn] = pvn
    return pxyHumVerts, humPxyVerts


def findPolys(context):
    hum,pxy = findHumanAndProxy(context)
    print(hum, pxy)
    humFaceVerts,humVertFaces = getVertFaces(hum)
    pxyFaceVerts,pxyVertFaces = getVertFaces(pxy)
    pxyHumVerts,humPxyVerts = assocPxyHumVerts(hum, pxy)
    print("PxyHumVerts", len(pxyHumVerts), len(humPxyVerts))

    pvn = len(pxy.data.vertices)
    pen = len(pxy.data.edges)
    newHumPxyVerts = {}
    newPxyEdges = []
    for e in hum.data.edges:
        if e.use_seam:
            hvn1,hvn2 = e.vertices
            pvn1 = humPxyVerts[hvn1]
            pvn2 = humPxyVerts[hvn2]
            useAdd = False
            if pvn1 is None or pvn2 is None:
                if hvn1 in newHumPxyVerts.keys():
                    pvn1 = newHumPxyVerts[hvn1]
                else:
                    pvn1 = newHumPxyVerts[hvn1] = pvn
                    pvn += 1
                if hvn2 in newHumPxyVerts.keys():
                    pvn2 = newHumPxyVerts[hvn2]
                else:
                    pvn2 = newHumPxyVerts[hvn2] = pvn
                    pvn += 1
                newPxyEdges.append((pen, pvn1, pvn2))
                pen += 1

    newVerts = [(pvn,hvn) for hvn,pvn in newHumPxyVerts.items()]
    newVerts.sort()

    setActiveObject(context, pxy)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='EDGE')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.mark_seam(clear=True)
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    print("BEF", len(pxy.data.vertices), len(pxy.data.edges))
    pxy.data.vertices.add(len(newVerts))
    for pvn,hvn in newVerts:
        pv = pxy.data.vertices[pvn]
        pv.co = hum.data.vertices[hvn].co.copy()
        #print(pv.index,pv.co)
    pxy.data.edges.add(len(newPxyEdges))
    for pen,pvn1,pvn2 in newPxyEdges:
        pe = pxy.data.edges[pen]
        pe.vertices = (pvn1,pvn2)
        pe.select = True
        #print(pe.index, list(pe.vertices), pe.use_seam)
    print("AFT", len(pxy.data.vertices), len(pxy.data.edges))
    return

    pxyHumFaces = {}
    for pfn,pfverts in enumerate(pxyFaceVerts):
        cands = []
        for pvn in pfverts:
            hvn = pxyHumVerts[pvn]
            for hfn in humVertFaces[hvn]:
                cands.append(hfn)
        print(pfn, cands)
        if len(cands) == 16:
            vcount = {}
            for hfn in cands:
                for hvn in humFaceVerts[hfn]:
                    if hvn not in vcount.keys():
                        vcount[hvn] = []
                    vcount[hvn].append(hfn)
            vlist = [(len(hfns),hvn,hfns) for hvn,hfns in vcount.items()]
            vlist.sort()
            print(vlist)
            pxyHumFaces[pfn] = vlist[-1]
            print("RES", pfn, pxyHumFaces[pfn])
            for hfn in vlist[-1][2]:
                hf = hum.data.polygons[hfn]
                hf.select = True


class DAZ_OT_FindPolys(bpy.types.Operator):
    bl_idname = "daz.find_polys"
    bl_label = "Find Polys"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return context.object

    def execute(self, context):
        checkObjectMode(context)
        try:
            findPolys(context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}

#-------------------------------------------------------------
#   Make faithful proxy
#-------------------------------------------------------------

class Proxifier:
    def __init__(self, ob):
        self.object = ob
        self.nfaces = len(ob.data.polygons)
        self.nverts = len(ob.data.vertices)
        self.faceverts = None
        self.vertfaces = None
        self.neighbors = None
        self.seams = None
        self.faces = []
        self.matOffset = 10
        self.origMnums = {}
        self.colorOnly = False


    def remains(self):
        free = [t for t in self.dirty.values() if not t]
        return len(free)


    def setup(self, ob, context):
        self.faceverts, self.vertfaces, self.neighbors, self.seams = findSeams(ob)
        if self.colorOnly:
            self.createMaterials()
        self.origMnums = {}
        for f in ob.data.polygons:
            self.origMnums[f.index] = f.material_index
            if self.colorOnly:
                f.material_index = 0

        deselectEverything(ob, context)
        self.dirty = dict([(fn,False) for fn in range(self.nfaces)])
        for f in ob.data.polygons:
            if f.hide:
                self.dirty[f.index] = True
        newfaces = [[fn] for fn in range(self.nfaces) if self.dirty[fn]]
        printStatistics(ob)
        return newfaces


    def getConnectedComponents(self):
        self.clusters = dict([(fn,-1) for fn in range(self.nfaces)])
        self.refs = dict([(fn,fn) for fn in range(self.nfaces)])
        cnum = 0
        for fn in range(self.nfaces):
            cnums = []
            for fn2 in self.neighbors[fn]:
                cn = self.clusters[fn2]
                if cn >= 0:
                    cnums.append(self.deref(cn))
            cnums.sort()
            if cnums:
                self.clusters[fn] = cn0 = cnums[0]
                for cn in cnums[1:]:
                    self.refs[cn] = cn0
            else:
                self.clusters[fn] = cn0 = cnum
                cnum += 1

        comps = dict([(cn,[]) for cn in range(cnum)])
        taken = dict([(cn,False) for cn in range(cnum)])
        for fn in range(self.nfaces):
            cn = self.clusters[fn]
            cn = self.deref(cn)
            comps[cn].append(fn)
            self.clusters[fn] = cn
        return comps,taken


    def deref(self, cn):
        cnums = []
        while self.refs[cn] != cn:
            cnums.append(cn)
            cn = self.refs[cn]
        for cn1 in cnums:
            self.refs[cn1] = cn
        return cn


    def getNodes(self):
        nodes = []
        comps,taken = self.getConnectedComponents()
        for vn in range(self.nverts):
            fnums = self.vertfaces[vn]
            if len(fnums) not in [0,2,4]:
                for fn in fnums:
                    if not self.dirty[fn]:
                        nodes.append(fn)
                        taken[self.clusters[fn]] = True
        for cn,comp in comps.items():
            if len(comp) > 0 and not taken[cn]:
                nodes.append(comp[0])
        return set(nodes)


    def make(self, ob, context):
        newfaces = self.setup(ob, context)
        remains1 = self.remains()
        print("Step 0 Remains:", remains1)

        nodes = self.getNodes()
        for fn in nodes:
            self.dirty[fn] = True
        for fn in nodes:
            self.mergeFaces(fn, newfaces)

        prevblock = newfaces
        step = 1
        remains2 = self.remains()
        while remains2 and remains2 < remains1 and step < 50:
            print("Step %d Remains:" % step, self.remains())
            block = []
            for newface in prevblock:
                self.mergeNextFaces(newface, block)
            newfaces += block
            prevblock = block
            step += 1
            remains1 = remains2
            remains2 = self.remains()
        print("Step %d Remains:" % step, self.remains())

        if self.colorOnly:
            self.combineFaces(newfaces)
            return
        else:
            self.buildNewMesh(newfaces)
        deleteMidpoints(ob)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles()
        bpy.ops.object.mode_set(mode='OBJECT')
        printStatistics(ob)


    def makeQuads(self, ob, context):
        newfaces = self.setup(ob, context)
        for fn1 in range(self.nfaces):
            if self.dirty[fn1]:
                continue
            if len(self.faceverts[fn1]) == 3:
                for fn2 in self.neighbors[fn1]:
                    if (len(self.faceverts[fn2]) == 3 and
                        not self.dirty[fn2] and
                        fn2 not in self.seams[fn1]):
                        self.dirty[fn1] = True
                        self.dirty[fn2] = True
                        newface = [fn1,fn2]
                        newfaces.append(newface)
                        break
        if self.colorOnly:
            self.combineFaces(newfaces)
            return
        else:
            self.buildNewMesh(newfaces)
        printStatistics(ob)


    def buildNewMesh(self, newfaces):
        from .geometry import makeNewUvloop

        free = [[fn] for fn,t in self.dirty.items() if not t]
        newfaces += free
        ob = self.object
        uvtex,uvloop,uvdata = getUvData(ob)
        self.vertmap = dict([(vn,-1) for vn in range(self.nverts)])
        self.verts = []
        self.lastvert = 0
        faces = []
        uvfaces = []
        mats = list(ob.data.materials)
        mnums = []
        n = 0
        for newface in newfaces:
            taken = self.findTaken(newface)
            n = 0
            fn1 = newface[n]
            fverts = self.faceverts[fn1]
            idx = 0
            vn = fverts[idx]
            while self.changeFace(vn, fn1, newface) >= 0:
                idx += 1
                if idx == len(fverts):
                    n += 1
                    if n == len(newface):
                        for fn in newface:
                            print(fn, self.faceverts[fn])
                        raise RuntimeError("BUG")
                    fn1 = newface[n]
                    fverts = self.faceverts[fn1]
                    idx = 0
                vn = fverts[idx]
            face = [self.getVert(vn)]
            uvface = [uvdata[fn1][idx]]
            mnums.append(self.origMnums[fn1])
            taken[vn] = True
            done = False
            while not done:
                fn2 = self.changeFace(vn, fn1, newface)
                if fn2 >= 0:
                    fn1 = fn2
                    fverts = self.faceverts[fn2]
                    idx = getIndex(vn, fverts)
                idx = (idx+1)%len(fverts)
                vn = fverts[idx]
                if taken[vn]:
                    done = True
                else:
                    face.append(self.getVert(vn))
                    uvface.append(uvdata[fn1][idx])
                    taken[vn] = True
            if len(face) >= 3:
                faces.append(face)
                uvfaces.append(uvface)
            else:
                print("Non-face:", face)

        me = bpy.data.meshes.new("New")
        me.from_pydata(self.verts, [], faces)
        uvloop = makeNewUvloop(me, "Uvloop", True)
        n = 0
        for uvface in uvfaces:
            for uv in uvface:
                uvloop.data[n].uv = uv
                n += 1
        for mat in mats:
            me.materials.append(mat)
        for fn,mn in enumerate(mnums):
            f = me.polygons[fn]
            f.material_index = mn
            f.use_smooth = True

        vgnames = [vgrp.name for vgrp in ob.vertex_groups]
        weights = dict([(vn,{}) for vn in range(self.nverts)])
        for vn,v in enumerate(ob.data.vertices):
            nvn = self.vertmap[vn]
            if nvn >= 0:
                for g in v.groups:
                    weights[nvn][g.group] = g.weight

        skeys = []
        if ob.data.shape_keys:
            for skey in ob.data.shape_keys.key_blocks:
                data = dict([(vn, skey.data[vn].co) for vn in range(self.nverts)])
                skeys.append((skey.name, skey.value, skey.slider_min, skey.slider_max, data))

        from .driver import getShapekeyDrivers, copyShapeKeyDrivers
        drivers = getShapekeyDrivers(ob)

        ob.data = me
        ob.vertex_groups.clear()
        vgrps = {}
        for gn,vgname in enumerate(vgnames):
            vgrps[gn] = ob.vertex_groups.new(name=vgname)
        for vn,grp in weights.items():
            for gn,w in grp.items():
                vgrps[gn].add([vn], w, 'REPLACE')

        for (sname, value, min, max, data) in skeys:
            skey = ob.shape_key_add(name=sname)
            skey.slider_min = min
            skey.slider_max = max
            skey.value = value
            for vn,co in data.items():
                nvn = self.vertmap[vn]
                if nvn >= 0:
                    skey.data[nvn].co = co

        copyShapeKeyDrivers(ob, drivers)


    def changeFace(self, vn, fn1, newface):
        for fn2 in newface:
            if (fn2 != fn1 and
                vn in self.faceverts[fn2]):
                return fn2
        return -1


    def getVert(self, vn):
        nvn = self.vertmap[vn]
        if nvn < 0:
            self.verts.append(self.object.data.vertices[vn].co)
            nvn = self.vertmap[vn] = self.lastvert
            self.lastvert += 1
        return nvn


    def findTaken(self, newface):
        taken = dict([vn,False] for fn in newface for vn in self.faceverts[fn])
        hits = dict([vn,0] for fn in newface for vn in self.faceverts[fn])
        for fn in newface:
            for vn in self.faceverts[fn]:
                hits[vn] += 1
                if hits[vn] > 2:
                    taken[vn] = True
        return taken


    def combineFaces(self, newfaces):
        ob = self.object
        maxmnum = self.colorFaces(newfaces)
        print("Max material number:", maxmnum)

        print("Adding faces")
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type='FACE')
        bpy.ops.mesh.select_all(action='DESELECT')
        count = 0
        for mn in range(maxmnum):
            if count % 25 == 0:
                print("  ", count)
            if mn % self.matOffset == 0:
                continue
            bpy.ops.object.mode_set(mode='OBJECT')
            ob.active_material_index = mn
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.object.material_slot_select()
            try:
                bpy.ops.mesh.edge_face_add()
            except RuntimeError:
                pass
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')
            count += 1

        printStatistics(ob)


    def mergeNextFaces(self, face, newfaces):
        me = self.object.data
        if len(face) < 2:
            return
        nextfaces = [face]
        while nextfaces:
            faces = nextfaces
            nextfaces = []
            for face in faces:
                for fn0 in face:
                    mn = self.origMnums[fn0]
                    for fn1 in face:
                        if (fn1 in self.neighbors[fn0] and
                            mn == self.origMnums[fn1]):
                            newface = self.mergeSide(fn0, fn1, newfaces, mn)
                            if newface:
                                if len(newface) == 4:
                                    for fn in newface:
                                        me.polygons[fn].select = True
                                    nextfaces.append(newface)
                                break


    def mergeSide(self, fn0, fn1, newfaces, mn):
        for fn2 in self.neighbors[fn0]:
            if (self.dirty[fn2] or
                fn2 in self.seams[fn0] or
                fn2 in self.seams[fn1]
                ):
                continue
            for fn3 in self.neighbors[fn1]:
                if (fn3 == fn2 or
                    self.dirty[fn3] or
                    fn3 not in self.neighbors[fn2] or
                    fn3 in self.seams[fn0] or
                    fn3 in self.seams[fn1] or
                    fn3 in self.seams[fn2]
                    ):
                    continue
                self.dirty[fn2] = True
                self.dirty[fn3] = True
                newface = self.mergeFacePair([fn2,fn3], newfaces, mn)
                return newface
        return None


    def mergeFaces(self, fn0, newfaces):
        newface = [fn0]
        self.dirty[fn0] = True
        mn = self.origMnums[fn0]
        for fn1 in self.neighbors[fn0]:
            if (fn1 not in self.seams[fn0] and
                not self.dirty[fn1] and
                mn == self.origMnums[fn1]):
                newface.append(fn1)
                self.dirty[fn1] = True
                break
        if len(newface) == 2:
            return self.mergeFacePair(newface, newfaces, mn)
        else:
            newfaces.append(newface)
            return newface


    def mergeFacePair(self, newface, newfaces, mn):
        fn0,fn1 = newface
        for fn2 in self.neighbors[fn0]:
           if (fn2 != fn1 and
                self.sharedVertex(fn1, fn2) and
                fn2 not in self.seams[fn0] and
                not self.dirty[fn2] and
                mn == self.origMnums[fn2]):
                newface.append(fn2)
                self.dirty[fn2] = True
                break

        if len(newface) == 3:
            fn2 = newface[2]
            for fn3 in self.neighbors[fn1]:
                if (fn3 != fn0 and
                    fn3 != fn2 and
                    fn3 in self.neighbors[fn2] and
                    not self.dirty[fn3] and
                    mn == self.origMnums[fn3]):
                    newface.append(fn3)
                    self.dirty[fn3] = True
                    break

        if len(newface) == 3:
            fn0,fn1,fn2 = newface
            self.dirty[fn2] = False
            newface = [fn0,fn1]

        newfaces.append(newface)
        return newface


    def sharedVertex(self, fn1, fn2):
        for vn in self.faceverts[fn1]:
            if vn in self.faceverts[fn2]:
                return True
        return False


    def colorFaces(self, newfaces):
        me = self.object.data
        matnums = dict((fn,0) for fn in range(self.nfaces))
        maxmnum = 0
        for newface in newfaces:
            mnums = []
            for fn in newface:
                mnums += [matnums[fn2] for fn2 in self.neighbors[fn]]
            mn = 1
            while mn in mnums:
                mn += 1
            if mn > maxmnum:
                maxmnum = mn
            for fn in newface:
                f = me.polygons[fn]
                f.material_index = matnums[fn] = mn

        return maxmnum


    def createMaterials(self):
        me = self.object.data
        mats = [mat for mat in me.materials]
        me.materials.clear()
        n = 0
        for r in range(3):
            for g in range(3):
                for b in range(3):
                    mat = bpy.data.materials.new("Mat-%02d" % n)
                    n += 1
                    mat.diffuse_color[0:3] = (r/2, g/2, b/2)
                    me.materials.append(mat)


    def selectRandomComponents(self, context):
        import random
        ob = context.object
        scn = context.scene
        deselectEverything(ob, context)
        self.faceverts, self.vertfaces = getVertFaces(ob)
        self.neighbors = findNeighbors(range(self.nfaces), self.faceverts, self.vertfaces)
        comps,taken = self.getConnectedComponents()
        for comp in comps.values():
            if random.random() > scn.DazRandomKeepFraction:
                for fn in comp:
                    f = ob.data.polygons[fn]
                    if not f.hide:
                        f.select = True
        bpy.ops.object.mode_set(mode='EDIT')


def getUvData(ob):
    from collections import OrderedDict

    uvtex = getUvTextures(ob.data)
    uvloop = ob.data.uv_layers[0]
    uvdata = OrderedDict()
    m = 0
    for fn,f in enumerate(ob.data.polygons):
        n = len(f.vertices)
        uvdata[fn] = [uvloop.data[j].uv for j in range(m,m+n)]
        m += n
    return uvtex,uvloop,uvdata


def deleteMidpoints(ob):
    edgeverts, vertedges = getVertEdges(ob)
    faceverts, vertfaces = getVertFaces(ob)
    uvtex,uvloop,uvdata = getUvData(ob)

    for vn,v in enumerate(ob.data.vertices):
        if (len(vertedges[vn]) == 2 and
            len(vertfaces[vn]) <= 2):
            e = vertedges[vn][0]
            vn1,vn2 = e.vertices
            if vn1 == vn:
                v.co = ob.data.vertices[vn2].co
                moveUv(vn, vn2, vertfaces[vn], faceverts, uvdata)
            elif vn2 == vn:
                v.co = ob.data.vertices[vn1].co
                moveUv(vn, vn1, vertfaces[vn], faceverts, uvdata)
            else:
                halt

    m = 0
    for uvs in uvdata.values():
        for j,uv in enumerate(uvs):
            uvloop.data[m+j].uv = uv
        m += len(uvs)


def moveUv(vn1, vn2, fnums, faceverts, uvdata):
    for fn in fnums:
        fverts = faceverts[fn]
        n1 = getIndex(vn1, fverts)
        n2 = getIndex(vn2, fverts)
        uvdata[fn][n1] = uvdata[fn][n2]


def getIndex(vn, verts):
    for n,vn1 in enumerate(verts):
        if vn1 == vn:
            return n


#-------------------------------------------------------------
#   Insert seams
#-------------------------------------------------------------

def insertSeams(hum, pxy):
    for pe in pxy.data.edges:
        pe.use_seam = False
    humPxy,pxyHum = identifyVerts(hum, pxy)

    pvn = pvn0 = len(pxy.data.vertices)
    pen = len(pxy.data.edges)
    newVerts = {}
    newEdges = {}
    seams = [e for e in hum.data.edges if e.use_seam]
    nseams = {}
    for e in seams:
        vn1,vn2 = e.vertices
        old1 = (vn1 in humPxy.keys())
        old2 = (vn2 in humPxy.keys())
        if old1 and old2:
            pvn1 = humPxy[vn1]
            pvn2 = humPxy[vn2]
            if (pvn1 in nseams.keys() and
                pvn2 not in nseams[pvn1]):
                newEdges[pen] = (pvn1, pvn2)
                pen += 1
        elif old1:
            pvn1 = humPxy[vn1]
            pvn2 = pvn
            newVerts[pvn2] = hum.data.vertices[vn2].co
            humPxy[vn2] = pvn2
            pvn += 1
            newEdges[pen] = (pvn1, pvn2)
            pen += 1
        elif old2:
            pvn1 = pvn
            newVerts[pvn1] = hum.data.vertices[vn1].co
            humPxy[vn1] = pvn1
            pvn2 = humPxy[vn2]
            pvn += 1
            newEdges[pen] = (pvn1, pvn2)
            pen += 1
        else:
            pvn1 = pvn
            newVerts[pvn1] = hum.data.vertices[vn1].co
            humPxy[vn1] = pvn1
            pvn2 = pvn+1
            newVerts[pvn2] = hum.data.vertices[vn2].co
            humPxy[vn2] = pvn2
            pvn += 2
            newEdges[pen] = (pvn1, pvn2)
            pen += 1

        if pvn1 not in nseams.keys():
            nseams[pvn1] = [pvn2]
        else:
            nseams[pvn1].append(pvn2)
        if pvn2 not in nseams.keys():
            nseams[pvn2] = [pvn1]
        else:
            nseams[pvn2].append(pvn1)

        if 1367 in [pvn1,pvn2]:
            print("O", vn1, vn2, pvn, pvn1, pvn2, old1, old2)
            print("  ", hum.data.vertices[vn1].co)
            print("  ", hum.data.vertices[vn2].co)
            print("  ", nseams[1367])
            print("  ", pxyHum[1367])


    pvn0 = len(pxy.data.vertices)
    pxy.data.vertices.add(len(newVerts))
    for pvn,co in newVerts.items():
        pxy.data.vertices[pvn].co = co
    #for pvn in range(pvn0, pvn0+3):
    #    print("  ", pvn, pxy.data.vertices[pvn].co)


    pxy.data.edges.add(len(newEdges))
    for pen,pverts in newEdges.items():
        pe = pxy.data.edges[pen]
        pe.vertices = pverts
        pe.select = True
    for pe in pxy.data.edges:
        pvn1,pvn2 = pe.vertices
        if (pvn1 in nseams.keys() and
            pvn2 in nseams[pvn1]):
            pe.use_seam = True


def identifyVerts(hum, pxy):
    '''
    for e in hum.data.edges:
        if e.use_seam:
            vn1,vn2 = e.vertices
            if vn1 < vn2:
                v1 = hum.data.vertices[vn1]
                v2 = hum.data.vertices[vn2]
                verts += [(v1.co, ("E", vn1, vn2, e.index)),
                          (v2.co, ("E", vn2, vn1, e.index))]
    '''
    hverts = [(v.co, ("H", v.index, v.co)) for v in hum.data.vertices]
    pverts = [(v.co, ("P", v.index, v.co)) for v in pxy.data.vertices]
    verts = hverts + pverts
    verts.sort()

    humPxy = {}
    pxyHum = {}
    nverts = len(verts)
    for m,vert in enumerate(verts):
        co1,data1 = vert
        if data1[0] == "P":
            mindist = 1e7
            pvn = data1[1]
            for j in range(-20,20):
                n = min(max(0, m+j), nverts-1)
                co2,data2 = verts[n]
                dist = (co1-co2).length
                if data2[0] == "H" and dist < mindist:
                    mindist = dist
                    vn = data2[1]
            humPxy[vn] = pvn
            pxyHum[pvn] = vn
            if mindist > 1e-7:
                pco = pxy.data.vertices[pvn]
                co = hum.data.vertices[vn]
                print("DIST", pvn, vn, pco, co, mindist)
    return humPxy, pxyHum


def deselectEverything(ob, context):
    setActiveObject(context, ob)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='FACE')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_mode(type='EDGE')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_mode(type='VERT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

#-------------------------------------------------------------
#   Make Proxy
#-------------------------------------------------------------

class MakeProxy():

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

    def execute(self, context):
        checkObjectMode(context)
        try:
            self.makeProxies(context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}

    def makeProxies(self, context):
        meshes,active = getSelectedObjects(context, 'MESH')
        print("-----")
        errors = []
        for ob in meshes:
            activateObject(context, ob)
            print("\nMake %s low-poly" % ob.name)
            self.makeProxy(ob, context, errors)
        restoreSelectedObjects(context, meshes, active)
        if errors:
            msg = "Cannot make low-poly version\nof meshes with shapekeys:"
            for ob in errors:
                msg += ("\n  %s" % ob.name)
            raise DazError(msg)


class DAZ_OT_MakeQuickProxy(MakeProxy, bpy.types.Operator):
    bl_idname = "daz.make_quick_proxy"
    bl_label = "Make Quick Low-poly"
    bl_description = "Replace all selected meshes by low-poly versions, using a quick algorithm that does not preserve UV seams"
    bl_options = {'UNDO'}

    def makeProxy(self, ob, context, errors):
        scn = context.scene
        if ob.data.shape_keys:
            errors.append(ob)
            return None
        applyShapeKeys(ob)
        printStatistics(ob)
        makeRawProxy(ob, scn.DazIterations)
        printStatistics(ob)
        return ob


class DAZ_OT_MakeFaithfulProxy(MakeProxy, bpy.types.Operator):
    bl_idname = "daz.make_faithful_proxy"
    bl_label = "Make Faithful Low-poly"
    bl_description = "Replace all selected meshes by low-poly versions, using a experimental algorithm that does preserve UV seams"
    bl_options = {'UNDO'}

    def makeProxy(self, ob, context, _errors):
        return Proxifier(ob).make(ob, context)


#-------------------------------------------------------------
#   Quadify
#-------------------------------------------------------------

class DAZ_OT_Quadify(MakeProxy, bpy.types.Operator):
    bl_idname = "daz.quadify"
    bl_label = "Quadify Triangles"
    bl_description = "Join triangles to quads"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

    def execute(self, context):
        meshes,active = getSelectedObjects(context, 'MESH')
        print("-----")
        errors = []
        for ob in meshes:
            activateObject(context, ob)
            print("\nQuadify %s" % ob.name)
            printStatistics(ob)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_mode(type='FACE')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.tris_convert_to_quads()
            bpy.ops.object.mode_set(mode='OBJECT')
            printStatistics(ob)
        restoreSelectedObjects(context, meshes, active)
        return {'FINISHED'}


def getSelectedObjects(context, type):
    objects = []
    for ob in getSceneObjects(context):
        if (getSelected(ob) and
            ob.type == type and
            not getattr(ob, HideViewport) and
            inSceneLayer(context, ob)):
            objects.append(ob)
    return objects, context.object


def restoreSelectedObjects(context, meshes, active):
    for ob in meshes:
        setSelected(ob, True)
    setActiveObject(context, active)

#-------------------------------------------------------------
#   Find seams
#-------------------------------------------------------------

def proxifyAll(context):
    duplets = {}
    dummy = bpy.data.meshes.new("Dummy")
    for ob in getSceneObjects(context):
        if ob.type == 'MESH':
            if ob.data.name in duplets.keys():
                duplets[ob.data.name].append(ob)
                ob.data = dummy
            else:
                duplets[ob.data.name] = []
    print("Making low-poly versions:")
    for ob in getSceneObjects(context):
        if (ob.type == 'MESH' and
            ob.data != dummy and
            getSelected(ob)):
            setActiveObject(context, ob)
            print("  %s: %d verts" % (ob.name, len(ob.data.vertices)))
            applyShapeKeys(ob)
            makeRawProxy(ob, scn.DazIterations)
    print("Restoring duplets")
    for mname,obs in duplets.items():
        me = bpy.data.meshes[mname]
        for ob in obs:
            ob.data = me
    bpy.data.meshes.remove(dummy)


class DAZ_OT_ProxifyAll(bpy.types.Operator, UseAllBool):
    bl_idname = "daz.proxify_all"
    bl_label = "Make All Low-Poly"
    bl_description = "Replace all (selected) meshes by low-poly versions"
    bl_options = {'UNDO'}

    def execute(self, context):
        checkObjectMode(context)
        try:
            proxifyAll(context, self.useAll)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}

#-------------------------------------------------------------
#   Split n-gons
#-------------------------------------------------------------

def splitNgons(ob, context):
    activateObject(context, ob)
    printStatistics(ob)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='FACE')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')
    for f in ob.data.polygons:
        if (len(f.vertices) > 4 and not f.hide):
            f.select = True
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.quads_convert_to_tris(ngon_method='BEAUTY')
    #bpy.ops.mesh.tris_convert_to_quads()
    bpy.ops.object.mode_set(mode='OBJECT')
    printStatistics(ob)


class DAZ_OT_SplitNgons(bpy.types.Operator):
    bl_idname = "daz.split_ngons"
    bl_label = "Split n-gons"
    bl_description = "Split all polygons with five or more corners into triangles"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return context.object and context.object.type == 'MESH'

    def execute(self, context):
        try:
            meshes,active = getSelectedObjects(context, 'MESH')
            for ob in meshes:
                print("\nSplit n-gons of %s" % ob.name)
                splitNgons(ob, context)
            restoreSelectedObjects(context, meshes, active)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}

#-------------------------------------------------------------
#   Find seams
#-------------------------------------------------------------

def findSeams(ob):
    print("Find seams", ob)
    #ob.data.materials.clear()

    faceverts,vertfaces = getVertFaces(ob)
    nfaces = len(faceverts)
    neighbors = findNeighbors(range(nfaces), faceverts, vertfaces)

    texverts,texfaces = findTexVerts(ob, vertfaces)
    _,texvertfaces = getVertFaces(ob, texverts, None, texfaces)
    texneighbors = findNeighbors(range(nfaces), texfaces, texvertfaces)

    seams = dict([(fn,[]) for fn in range(nfaces)])
    for fn1,nn1 in neighbors.items():
        for fn2 in nn1:
            if (fn2 not in texneighbors[fn1]):
                if fn1 in seams.keys():
                    seams[fn1].append(fn2)

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='EDGE')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.mark_seam(clear=True)
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    for e in ob.data.edges:
        vn1,vn2 = e.vertices
        for fn1 in vertfaces[vn1]:
            f1 = ob.data.polygons[fn1]
            for fn2 in vertfaces[vn2]:
                f2 = ob.data.polygons[fn2]
                if (vn2 in f1.vertices and
                    vn1 in f2.vertices and
                    fn1 != fn2):
                    if fn2 in seams[fn1]:
                        e.select = True

    _,vertedges = getVertEdges(ob)
    _,edgefaces = getEdgeFaces(ob, vertedges)
    for e in ob.data.edges:
        if len(edgefaces[e.index]) != 2:
            e.select = True

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.mark_seam(clear=False)
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    print("Seams found")
    return  faceverts, vertfaces, neighbors,seams


class DAZ_OT_FindSeams(bpy.types.Operator):
    bl_idname = "daz.find_seams"
    bl_label = "Find Seams"
    bl_description = "Create seams based on existing UVs"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return context.object and context.object.type == 'MESH'

    def execute(self, context):
        checkObjectMode(context)
        try:
            findSeams(context.object)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}

#-------------------------------------------------------------
#   Select random strands
#-------------------------------------------------------------

class DAZ_OT_SelectRandomStrands(bpy.types.Operator):
    bl_idname = "daz.select_random_strands"
    bl_label = "Select Random Strands"
    bl_description = "Select random subset of strands selected in UV space"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return context.object and context.object.type == 'MESH'

    def execute(self, context):
        checkObjectMode(context)
        try:
            ob = context.object
            Proxifier(ob).selectRandomComponents(context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}

#-------------------------------------------------------------
#  Apply morphs
#-------------------------------------------------------------

def applyShapeKeys(ob):
    from .morphing import getShapeKeyCoords
    if ob.type != 'MESH':
        return
    if ob.data.shape_keys:
        skeys,coords = getShapeKeyCoords(ob)
        skeys.reverse()
        for skey in skeys:
            ob.shape_key_remove(skey)
        skey = ob.data.shape_keys.key_blocks[0]
        ob.shape_key_remove(skey)
        for v in ob.data.vertices:
            v.co = coords[v.index]


class DAZ_OT_ApplyMorphs(bpy.types.Operator):
    bl_idname = "daz.apply_morphs"
    bl_label = "Apply Morphs"
    bl_description = "Apply all shapekeys"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return context.object and context.object.type == 'MESH'

    def execute(self, context):
        checkObjectMode(context)
        try:
            for ob in getSceneObjects(context):
                if getSelected(ob):
                    applyShapeKeys(ob)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}

#-------------------------------------------------------------
#   Print statistics
#-------------------------------------------------------------

def printStatistics(ob):
    print("Verts: %d, Edges: %d, Faces: %d" %
        (len(ob.data.vertices), len(ob.data.edges), len(ob.data.polygons)))


class DAZ_OT_PrintStatistics(bpy.types.Operator):
    bl_idname = "daz.print_statistics"
    bl_label = "Print Statistics"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return context.object and context.object.type == 'MESH'

    def execute(self, context):
        checkObjectMode(context)
        print("--------- Statistics ------------")
        try:
            for ob in getSceneObjects(context):
                if getSelected(ob) and ob.type == 'MESH':
                    print("Object: %s" % ob.name)
                    printStatistics(ob)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}

#-------------------------------------------------------------
#   Add mannequin
#-------------------------------------------------------------

def remapBones(bone, scn, vgrps, majors, remap):
    special = {
        'SOLID' : ["head"],
        'JAW' : ["head", "lowerjaw", "leye", "reye"],
        'FULL' : []
          }
    if bone.name.lower() in special[scn.DazMannequinHead]:
        if bone.name in vgrps.keys():
            remap = vgrps[bone.name].index
    elif remap is not None:
        if bone.name in vgrps.keys():
            gn = vgrps[bone.name].index
            if gn in majors.keys():
                majors[remap] += majors[gn]
                del majors[gn]
    for child in bone.children:
        remapBones(child, scn, vgrps, majors, remap)


def addMannequins(context):
    objects = getSceneObjects(context)
    selected = [ob for ob in objects if getSelected(ob)]
    ob = context.object
    rig = ob.parent
    if not (rig and rig.type == 'ARMATURE'):
        raise DazError("Mesh %s has no armature parent" % ob)
    setActiveObject(context, rig)
    bpy.ops.object.mode_set(mode='OBJECT')
    oldlayers = list(rig.data.layers)
    rig.data.layers = 32*[True]

    # Create group/collection
    mangrp = None
    scn = context.scene
    coll = getCollection(context)
    if not scn.DazUseMannequinGroup:
        pass
    elif bpy.app.version <= (2,80,0):
        for grp in bpy.data.groups:
            if grp.name == scn.DazMannequinGroup:
                mangrp = grp
                break
        if mangrp is None:
            mangrp = bpy.data.groups.new(scn.DazMannequinGroup)
        if rig.name not in mangrp.objects.keys():
            mangrp.objects.link(rig)
    else:
        coll = None
        for coll1 in scn.collection.children:
            if coll1.name == scn.DazMannequinGroup:
                coll = coll1
                break
        if coll is None:
            coll = bpy.data.collections.new(name=scn.DazMannequinGroup)
            scn.collection.children.link(coll)
        if rig.name not in coll.objects.keys():
            coll.objects.link(rig)

    # Add mannequin objects for selected meshes
    meshes = [ob for ob in objects if (getSelected(ob) and ob.type == 'MESH')]
    for ob in meshes:
        addMannequin(ob, context, rig, coll, mangrp)
        
    for ob in getSceneObjects(context):
        if ob in selected:
            setSelected(ob, True)
        else:
            setSelected(ob, False)
    rig.data.layers = oldlayers


def addMannequin(ob, context, rig, coll, mangrp):
    from random import random
    from .node import setParent
    from .guess import getSkinMaterial

    scn = context.scene
    mat = bpy.data.materials.new("%sMannequin" % ob.name)
    mat.diffuse_color[0:3] = (random(), random(), random())
    for omat in ob.data.materials:
        mat.diffuse_color = omat.diffuse_color
        data = getSkinMaterial(omat)
        if data and data[0] == 'Skin':
            break

    faceverts, vertfaces = getVertFaces(ob)
    majors = {}
    skip = []
    for vgrp in ob.vertex_groups:
        if vgrp.name in rig.data.bones:
            majors[vgrp.index] = []
        else:
            skip.append(vgrp.index)
    for v in ob.data.vertices:
        wmax = 1e-3
        vbest = None
        for g in v.groups:
            if g.weight > wmax and g.group not in skip:
                wmax = g.weight
                vbest = v
                gbest = g.group
        if vbest is not None:
            majors[gbest].append(vbest)

    roots = [bone for bone in rig.data.bones if bone.parent is None]
    for bone in roots:
        remapBones(bone, scn, ob.vertex_groups, majors, None)

    obverts = ob.data.vertices
    vmax = 0.49
    if ob.data.shape_keys:
        for skey in ob.data.shape_keys.key_blocks:
            if skey.value > vmax:
                print("Using shapekey %s for %s locations" % (skey.name, ob.name))
                obverts = skey.data
                vmax = skey.value
    
    nobs = []
    for vgrp in ob.vertex_groups:
        if (vgrp.name not in rig.pose.bones.keys() or
            vgrp.index not in majors.keys()):
            continue
        fnums = []
        for v in majors[vgrp.index]:
            for fn in vertfaces[v.index]:
                fnums.append(fn)
        fnums = list(set(fnums))

        nverts = []
        nfaces = []
        for fn in fnums:
            f = ob.data.polygons[fn]
            nverts += f.vertices
            nfaces.append(f.vertices)
        if not nfaces:
            continue
        nverts = list(set(nverts))
        nverts.sort()

        bone = rig.data.bones[vgrp.name]
        head = bone.head_local
        verts = [obverts[vn].co-head for vn in nverts]
        assoc = dict([(vn,n) for n,vn in enumerate(nverts)])
        faces = []
        for fverts in nfaces:
            faces.append([assoc[vn] for vn in fverts])

        name = ob.name[0:3] + "_" + vgrp.name
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        nob = bpy.data.objects.new(name, me)
        coll.objects.link(nob)
        nob.location = head
        nob.lock_location = nob.lock_rotation = nob.lock_scale = (True,True,True)
        nobs.append((nob, rig, bone, me))

    updateScene(context, updateDepsGraph=True)
    for nob, rig, bone, me in nobs:
        setParent(context, nob, rig, bone.name, update=False)
        nob.DazMannequin = True
        if mangrp:
            mangrp.objects.link(nob)
        me.materials.append(mat)
    return nobs


class DAZ_OT_AddMannequin(bpy.types.Operator):
    bl_idname = "daz.add_mannequin"
    bl_label = "Add Mannequins"
    bl_description = "Add mannequins to selected meshes. Don't change rig after this."
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return context.object and context.object.type == 'MESH'

    def execute(self, context):
        checkObjectMode(context)
        try:
            addMannequins(context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}

#-------------------------------------------------------------
#   Add push
#-------------------------------------------------------------

def addPush(context):
    hasShapeKeys = []
    for ob in getSceneObjects(context):
        if getSelected(ob) and ob.type == 'MESH':
            #applyShapeKeys(ob)
            if ob.data.shape_keys:
                hasShapeKeys.append(ob)
            else:
                basic = ob.shape_key_add(name="Basic")
            skey = ob.shape_key_add(name="Push")
            scale = ob.DazScale
            for n,v in enumerate(ob.data.vertices):
                skey.data[n].co += v.normal*scale
    if hasShapeKeys:
        msg = ("Push added to meshes with shapekeys:\n  " + "\n  ".join([ob.name for ob in hasShapeKeys]))
        raise DazError(msg, True)


class DAZ_OT_AddPush(bpy.types.Operator):
    bl_idname = "daz.add_push"
    bl_label = "Add Push"
    bl_description = "Add a push shapekey"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return context.object and context.object.type == 'MESH'

    def execute(self, context):
        checkObjectMode(context)
        try:
            addPush(context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}

#-------------------------------------------------------------
#   Add subsurf
#-------------------------------------------------------------

def addSubsurf(context):
    for ob in getSceneObjects(context):
        if getSelected(ob) and ob.type == 'MESH':
            mod = ob.modifiers.new('SUBSURF', 'SUBSURF')
            mod.levels = 0
            mod.render_levels = 1


class DAZ_OT_AddSubsurf(bpy.types.Operator):
    bl_idname = "daz.add_subsurf"
    bl_label = "Add Subsurf"
    bl_description = "Add a subsurf modifier"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return context.object and context.object.type == 'MESH'

    def execute(self, context):
        checkObjectMode(context)
        try:
            addSubsurf(context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}

#-------------------------------------------------------------
#   Make deflection
#-------------------------------------------------------------

class DAZ_OT_MakeDeflection(bpy.types.Operator):
    bl_idname = "daz.make_deflection"
    bl_label = "Make Deflection"
    bl_description = "Make a deflection object"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return context.object and context.object.type == 'MESH'

    def execute(self, context):
        try:
            self.make(context)
        except DazError:
            handleDazError(context)
        return {'FINISHED'}

    def make(self, context):
        from .load_json import loadJson
        ob = context.object
        coll = getCollection(context)
        folder = os.path.dirname(__file__)
        filepath = os.path.join(folder, "data", "lowpoly", ob.DazMesh.lower()+".json")
        print(filepath)
        struct = loadJson(filepath, mustOpen=True)
        vnums = struct["vertices"]
        verts = [ob.data.vertices[vn].co for vn in struct["vertices"]]
        faces = struct["faces"]
        me = bpy.data.meshes.new(ob.data.name+"Deflect")
        me.from_pydata(verts, [], faces)
        nob = bpy.data.objects.new(ob.name+"Deflect", me)
        coll.objects.link(nob)
        setActiveObject(context, nob)

        vgrps = dict([(vgrp.index, vgrp) for vgrp in ob.vertex_groups])
        ngrps = {}
        for vgrp in ob.vertex_groups:
            ngrp = nob.vertex_groups.new(name=vgrp.name)
            ngrps[ngrp.index] = ngrp
        for nv in nob.data.vertices:
            v = ob.data.vertices[vnums[nv.index]]
            for g in v.groups:
                ngrp = ngrps[g.group]
                ngrp.add([nv.index], g.weight, 'REPLACE')

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_FindPolys,
    DAZ_OT_MakeQuickProxy,
    DAZ_OT_MakeFaithfulProxy,
    DAZ_OT_Quadify,
    DAZ_OT_ProxifyAll,
    DAZ_OT_SplitNgons,
    DAZ_OT_FindSeams,
    DAZ_OT_SelectRandomStrands,
    DAZ_OT_ApplyMorphs,
    DAZ_OT_PrintStatistics,
    DAZ_OT_AddMannequin,
    DAZ_OT_AddPush,
    DAZ_OT_AddSubsurf,
    DAZ_OT_MakeDeflection,
]

def initialize():
    from bpy.props import BoolProperty, EnumProperty, StringProperty

    bpy.types.Object.DazMannequin = BoolProperty(default = False)

    bpy.types.Scene.DazMannequinHead = EnumProperty(
        items = [('SOLID', "Solid", "Solid head"),
                 ('JAW', "Jaw", "Head with jaws and eyes"),
                 ('FULL', "Full", "Head with all face bones"),
                 ],
        name = "Head",
        description = "How to make the mannequin head",
        default = 'JAW')

    if bpy.app.version <= (2,80,0):
        usename = "Add To Group"
        usedesc = "Add mannequin to group"
        grpname = "Group"
        grpdesc = "Add mannequin to this group"
    else:
        usename = "Add To Collection"
        usedesc = "Add mannequin to collection"
        grpname = "Collection"
        grpdesc = "Add mannequin to this collection"

    bpy.types.Scene.DazUseMannequinGroup = BoolProperty(
        name = usename,
        description = usedesc,
        default = True)

    bpy.types.Scene.DazMannequinGroup = StringProperty(
        name = grpname,
        description = grpdesc,
        default = "Mannequin")

    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)




