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

def getVertFaces(ob, verts=None, faces=None, faceverts=None):
    if verts is None:
        verts = range(len(ob.data.vertices))
    if faces is None:
        faces = range(len(ob.data.polygons))
    if faceverts is None:
        faceverts = [list(f.vertices) for f in ob.data.polygons]
    vertfaces = dict([(vn,[]) for vn in verts])
    for fn in faces:
        for vn in faceverts[fn]:
            vertfaces[vn].append(fn)
    return faceverts, vertfaces


def getVertEdges(ob, edgeverts=None):
    nverts = len(ob.data.vertices)
    nedges = len(ob.data.edges)
    if edgeverts is None:
        edgeverts = dict([(e.index, e.vertices) for e in ob.data.edges])
    vertedges = dict([(vn,[]) for vn in range(nverts)])
    for e in ob.data.edges:
        for vn in edgeverts[e.index]:
            vertedges[vn].append(e)
    return edgeverts, vertedges


def otherEnd(vn, e):
    vn1,vn2 = e.vertices
    if vn == vn1:
        return vn2
    else:
        return vn1


def getEdgeFaces(ob, vertedges=None):
    if vertedges is None:
        _,vertedges = getVertEdges(ob)
    nedges = len(ob.data.edges)
    nfaces = len(ob.data.polygons)
    faceedges = dict([(fn,[]) for fn in range(nfaces)])
    edgefaces = dict([(en,[]) for en in range(nedges)])
    for f in ob.data.polygons:
        for vn1,vn2 in f.edge_keys:
            for e in vertedges[vn1]:
                if vn2 in e.vertices:
                    en = e.index
                    if en not in faceedges[f.index]:
                        faceedges[f.index].append(en)
                    edgefaces[en].append(f.index)
    return faceedges,edgefaces


def getConnectedVerts(ob):
    nverts = len(ob.data.vertices)
    connected = dict([(vn,[]) for vn in range(nverts)])
    for e in ob.data.edges:
        vn1,vn2 = e.vertices
        connected[vn1].append(vn2)
        connected[vn2].append(vn1)
    return connected


def getSharedPolys(ob):
    nverts = len(ob.data.vertices)
    shared = dict([(vn,[]) for vn in range(nverts)])
    for f in ob.data.polygons:
        for vn1 in f.vertices:
            for vn2 in f.vertices:
                if (vn1 != vn2 and vn2 not in shared[vn1]):
                    shared[vn1].append(vn2)
                    shared[vn2].append(vn1)
    return shared


def findNeighbors(faces, faceverts, vertfaces):
    neighbors = dict([(fn,[]) for fn in faces])
    for fn1 in faces:
        for v1n in faceverts[fn1]:
            for fn2 in vertfaces[v1n]:
                if (fn2 == fn1 or
                    fn2 in neighbors[fn1]):
                    continue
                for v2n in faceverts[fn2]:
                    if (v1n != v2n and
                        fn1 in vertfaces[v2n]):
                        if fn2 not in neighbors[fn1]:
                            neighbors[fn1].append(fn2)
                        if fn1 not in neighbors[fn2]:
                            neighbors[fn2].append(fn1)

    return neighbors


def removeDuplicates(face):
    vn1 = face[0]
    nface = [vn1]
    for vn2 in face[1:]:
        if vn1 != vn2:
            nface.append(vn2)
        vn1 = vn2
    return nface


def duplicates(face):
    face = face.copy()
    face.sort()
    vn1 = face[0]
    for vn2 in face[1:]:
        if vn1 == vn2:
            return True
        vn1 = vn2
    return False

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def findTexVerts(ob, vertfaces):
    nfaces = len(ob.data.polygons)
    touches = dict([(fn,[]) for fn in range(nfaces)])
    for f1 in ob.data.polygons:
        fn1 = f1.index
        for vn in f1.vertices:
            for fn2 in vertfaces[vn]:
                if fn1 != fn2:
                    touches[fn1].append(fn2)

    uvs = ob.data.uv_layers.active.data
    uvindices = {}
    m = 0
    for f in ob.data.polygons:
        nv = len(f.vertices)
        uvindices[f.index] = range(m, m+nv)
        m += nv

    texverts = {}
    texfaces = {}
    vt = 0
    vts = {}
    for fn1 in range(nfaces):
        texfaces[fn1] = texface = []
        touches[fn1].sort()
        for m1 in uvindices[fn1]:
            test = False
            matched = False
            uv1 = uvs[m1].uv
            for fn2 in touches[fn1]:
                if fn2 < fn1:
                    for m2 in uvindices[fn2]:
                        uv2 = uvs[m2].uv
                        if (uv1-uv2).length < 2e-4:
                            if m2 < m1:
                                vts[m1] = vts[m2]
                            else:
                                vts[m2] = vts[m1]
                            matched = True
                            #break
            if not matched:
                vts[m1] = vt
                texverts[vt] = uvs[m1].uv
                vt += 1
            texface.append(vts[m1])
    return texverts, texfaces

