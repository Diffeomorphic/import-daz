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

import sys
import bpy
from bpy.props import *
from mathutils import Vector
from math import floor
from .error import *
from .utils import *
from .tables import *

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def findCenters(ob):
    vs = ob.data.vertices
    uvs = ob.data.uv_layers.active.data
    centers = {}
    uvcenters = {}
    m = 0
    for f in ob.data.polygons:
        f.select = True
        fn = f.index
        if len(f.vertices) == 4:
            vn0,vn1,vn2,vn3 = f.vertices
            centers[fn] = (vs[vn0].co+vs[vn1].co+vs[vn2].co+vs[vn3].co)/4
            uvcenters[fn] = (uvs[m].uv+uvs[m+1].uv+uvs[m+2].uv+uvs[m+3].uv)/4
            m += 4
        else:
            vn0,vn1,vn2 = f.vertices
            centers[fn] = (vs[vn0].co+vs[vn1].co+vs[vn2].co)/4
            uvcenters[fn] = (uvs[m].uv+uvs[m+1].uv+uvs[m+2].uv)/4
            m += 3
        f.select = False
    return centers, uvcenters


#-------------------------------------------------------------
#   Collect rectangles
#-------------------------------------------------------------

def collectRects(faceverts, neighbors, test=False):
    #fclusters = dict([(fn,-1) for fn,_ in faceverts])
    fclusters = {}
    for fn,_ in faceverts:
        fclusters[fn] = -1
        for nn in neighbors[fn]:
            fclusters[nn] = -1
    clusters = {-1 : -1}
    nclusters = 0

    for fn,_ in faceverts:
        fncl = [deref(nn, fclusters, clusters) for nn in neighbors[fn] if nn < fn]
        if fncl == []:
            cn = clusters[cn] = nclusters
            nclusters += 1
        else:
            cn = min(fncl)
            for cn1 in fncl:
                clusters[cn1] = cn
        fclusters[fn] = cn

    for fn,_ in faceverts:
        fclusters[fn] = deref(fn, fclusters, clusters)

    rects = []
    for cn in clusters.keys():
        if cn == clusters[cn]:
            faces = [fn for fn,_ in faceverts if fclusters[fn] == cn]
            vertsraw = [vs for fn,vs in faceverts if fclusters[fn] == cn]
            vstruct = {}
            for vlist in vertsraw:
                for vn in vlist:
                    vstruct[vn] = True
            verts = list(vstruct.keys())
            verts.sort()
            rects.append((verts, faces))
            if len(rects) > 1000:
                print("Too many rects")
                return rects, clusters, fclusters

    return rects, clusters, fclusters


def deref(fn, fclusters, clusters):
    cn = fclusters[fn]
    updates = []
    while cn != clusters[cn]:
        updates.append(cn)
        cn = clusters[cn]
    for nn in updates:
        clusters[nn] = cn
    fclusters[fn] = cn
    return cn



def selectFaces(ob, faces):
    for fn in faces:
        ob.data.polygons[fn].select = True


def quadsOnly(ob, faces):
    for fn in faces:
        f = ob.data.polygons[fn]
        if len(f.vertices) != 4:
            print("  Face %d has %s corners" % (fn, len(f.vertices)))
            return False
    return True

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def findStartingPoint(ob, neighbors, uvcenters):
    types = dict([(n,[]) for n in range(1,5)])
    for fn,neighs in neighbors.items():
        nneighs = len(neighs)
        if nneighs not in types.keys():
            print("  Face %d has %d neighbors" % (fn, nneighs))
            #selectFaces(ob, [fn]+neighs)
            return None,None,None,None
        types[nneighs].append(fn)

    singlets = [(uvcenters[fn][0]+uvcenters[fn][1], fn) for fn in types[1]]
    singlets.sort()
    if len(singlets) > 0:
        if len(singlets) != 2:
            print("  Has %d singlets" % len(singlets))
            return None,None,None,None
        if (types[3] != [] or types[4] != []):
            print("  Has 2 singlets, %d triplets and %d quadruplets" % (len(types[3]), len(types[4])))
            return None,None,None,None
        first = singlets[0][1]
        corner = types[1]
        boundary = types[2]
        bulk = types[3]
    else:
        doublets = [(uvcenters[fn][0]+uvcenters[fn][1], fn) for fn in types[2]]
        doublets.sort()
        if len(doublets) > 4:
            print("  Has %d doublets" % len(doublets))
            selectFaces(ob, [fn for _,fn in doublets])
            return None,None,None,None
        if len(doublets) < 4:
            if len(doublets) == 2:
                print("  Has %d doublets" % len(doublets))
                selectFaces(ob, neighbors.keys())
            return None,None,None,None
        first = doublets[0][1]
        corner = types[2]
        boundary = types[3]
        bulk = types[4]

    return first, corner, boundary, bulk


def sortColumns(first, corner, boundary, bulk, neighbors, uvcenters):
    column = getDown(first, neighbors, corner, boundary, uvcenters)
    columns = [column]
    if len(corner) <= 2:
        return columns
    fn = first
    n = 0
    while (True):
        n += 1
        horizontal = [(uvcenters[nb][0], nb) for nb in neighbors[fn]]
        horizontal.sort()
        fn = horizontal[-1][1]
        if n > 50:
            return columns
        elif fn in corner:
            column = getDown(fn, neighbors, corner, boundary, uvcenters)
            columns.append(column)
            return columns
        elif fn in boundary:
            column = getDown(fn, neighbors, boundary, bulk, uvcenters)
            columns.append(column)
        else:
            print("Hair bug", fn)
            return None
            raise DazError("Hair bug")
    print("Sorted")


def getDown(top, neighbors, boundary, bulk, uvcenters):
    column = [top]
    fn = top
    n = 0
    while (True):
        n += 1
        vertical = [(uvcenters[nb][1], nb) for nb in neighbors[fn]]
        vertical.sort()
        fn = vertical[-1][1]
        if fn in boundary or n > 500:
            column.append(fn)
            column.reverse()
            return column
        else:
            column.append(fn)


def getColumnCoords(columns, centers):
    #print("Get column coords")
    length = len(columns[0])
    hcoords = []
    short = False
    for column in columns:
        if len(column) < length:
            length = len(column)
            short = True
        hcoord = [centers[fn] for fn in column]
        hcoords.append(hcoord)
    if short:
        hcoords = [hcoord[0:length] for hcoord in hcoords]
    return hcoords


def resizeStrand(strand, n):
    m = len(strand)
    step = (m-1)/(n-1)
    nstrand = []
    for i in range(n-1):
        j = floor(i*step + 1e-4)
        x = strand[j]
        y = strand[j+1]
        eps = i*step - j
        z = eps*y + (1-eps)*x
        nstrand.append(z)
    nstrand.append(strand[m-1])
    return nstrand


#-------------------------------------------------------------
#   Make Hair
#-------------------------------------------------------------

def getHairAndHuman(context, strict):
    hair = context.object
    hum = None
    for ob in getSceneObjects(context):
        if getSelected(ob) and ob.type == 'MESH' and ob != hair:
            hum = ob
            break
    if strict and hum is None:
        raise DazError("Select hair and human")
    return hair,hum


def makeHair(context):
    scn = context.scene
    hair,hum = getHairAndHuman(context, True)
    print("HH", hair, hum)
    #vgrp = createSkullGroup(hum, scn)

    setActiveObject(context, hum)
    clearHair(hum, hair, scn.DazHairColor, scn)
    hsystems = {}

    setActiveObject(context, hair)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='FACE')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    print("Find neighbors")
    faceverts,vertfaces = getVertFaces(hair)
    nfaces = len(hair.data.polygons)
    neighbors = findNeighbors(range(nfaces), faceverts, vertfaces)
    centers,uvcenters = findCenters(hair)

    print("Collect rects")
    ordfaces = [(f.index,f.vertices) for f in hair.data.polygons]
    rects1,_,_ = collectRects(ordfaces, neighbors)

    print("Find texverts")
    texverts,texfaces = findTexVerts(hair, vertfaces)
    print("Find tex neighbors", len(texverts), nfaces, len(texfaces))
    # Improve
    _,texvertfaces = getVertFaces(hair, texverts, None, texfaces)
    neighbors = findNeighbors(range(nfaces), texfaces, texvertfaces)

    rects = []
    print("Collect texrects")
    for verts1,faces1 in rects1:
        texfaces1 = [(fn,texfaces[fn]) for fn in faces1]
        nn = [(fn,neighbors[fn]) for fn in faces1]
        rects2,clusters,fclusters = collectRects(texfaces1, neighbors, True)
        for rect in rects2:
            rects.append(rect)

    print("Sort columns")
    haircount = -1
    setActiveObject(context, hair)
    verts = range(len(hair.data.vertices))
    count = 0
    for _,faces in rects:
        if count % 10 == 0:
            sys.stdout.write(".")
            sys.stdout.flush()
        count += 1
        if not quadsOnly(hair, faces):
            continue
        _,vertfaces = getVertFaces(None, verts, faces, faceverts)
        neighbors = findNeighbors(faces, faceverts, vertfaces)
        if neighbors is None:
            continue
        first, corner, boundary, bulk = findStartingPoint(hair, neighbors, uvcenters)
        if first is None:
            continue
        selectFaces(hair, faces)
        columns = sortColumns(first, corner, boundary, bulk, neighbors, uvcenters)
        if columns:
            strands = getColumnCoords(columns, centers)
            for strand in strands:
                haircount += 1
                if haircount % scn.DazHairSparsity != 0:
                    continue
                n = len(strand)
                if n not in hsystems.keys():
                    hsystems[n] = []
                hsystems[n].append(strand)

    print("Total number of strands: %d" % (haircount+1))

    if scn.DazResizeInBlocks:
        print("Resize hair in blocks of ten")
        nsystems = {}
        for strands in hsystems.values():
            for strand in strands:
                n = 10*((len(strand)+5)//10)
                if n < 10:
                    n = 10
                nstrand = resizeStrand(strand, n)
                if n in nsystems.keys():
                    nsystems[n].append(nstrand)
                else:
                    nsystems[n] = [nstrand]
        hsystems = nsystems

    elif scn.DazResizeHair:
        print("Resize hair")
        nstrands = []
        for strands in hsystems.values():
            for strand in strands:
                nstrand = resizeStrand(strand, scn.DazHairSize)
                nstrands.append(nstrand)
        hsystems = {scn.DazHairSize: nstrands}

    print("Make particle hair")
    setActiveObject(context, hum)
    addHair(hum, hsystems, scn)
    setActiveObject(context, hair)
    print("Done")

# ---------------------------------------------------------------------
#
# ---------------------------------------------------------------------

def clearHair(hum, hair, color, scn):
    nsys = len(hum.particle_systems)
    for n in range(nsys):
        bpy.ops.object.particle_system_remove()
    mat = bpy.data.materials.new("Hair")
    buildHairMaterial(mat, color, scn)
    hum.data.materials.append(mat)


def createSkullGroup(hum, scn):
    if scn.DazSkullGroup == 'TOP':
        maxheight = -1e4
        for v in hum.data.vertices:
            if v.co[2] > maxheight:
                maxheight = v.co[2]
                top = v.index
        vgrp = hum.vertex_groups.new(name="Skull")
        vgrp.add([top], 1.0, 'REPLACE')
        return vgrp
    elif scn.DazSkullGroup == 'ALL':
        vgrp = hum.vertex_groups.new(name="Skull")
        for vn in range(len(hum.data.vertices)):
            vgrp.add([vn], 1.0, 'REPLACE')
        return vgrp
    else:
        return None


def addHair(hum, hsystems, scn, useHairDynamics=False):
    vgrp = createSkullGroup(hum, scn)
    for strands in hsystems.values():
        hlen = int(len(strands[0]))
        if hlen < 3:
            continue
        bpy.ops.object.particle_system_add()
        psys = hum.particle_systems.active
        psys.name = "Hair-%02d" % hlen
        if vgrp:
            psys.vertex_group_density = vgrp.name

        pset = psys.settings
        pset.type = 'HAIR'
        pset.use_strand_primitive = True
        useEmitter = (scn.DazSkullGroup == 'TOP')
        if hasattr(pset, "use_render_emitter"):
            pset.use_render_emitter = useEmitter
        elif hasattr(hum, "show_instancer_for_render"):
            hum.show_instancer_for_render = useEmitter
        pset.render_type = 'PATH'
        pset.child_type = 'SIMPLE'

        pset.material = len(hum.data.materials)
        pset.path_start = 0
        pset.path_end = 1
        pset.count = int(len(strands))
        pset.hair_step = hlen-1
        pset.child_nbr = 1
        pset.rendered_child_count = 10
        pset.child_radius = 2*hum.DazScale

        if hasattr(pset, "cycles_curve_settings"):
            ccset = pset.cycles_curve_settings
        elif hasattr(pset, "cycles"):
            ccset = pset.cycles
        else:
            ccset = pset
        if hasattr(ccset, "root_width"):
            ccset.root_width = 1.0
            ccset.tip_width = 0
        else:
            ccset.root_radius = 1.0
            ccset.tip_radius = 0
        ccset.radius_scale = 0.1*hum.DazScale

        bpy.ops.object.mode_set(mode='PARTICLE_EDIT')
        pedit = scn.tool_settings.particle_edit
        pedit.use_emitter_deflect = False
        pedit.use_preserve_length = False
        pedit.use_preserve_root = False
        hum.data.use_mirror_x = False
        pedit.select_mode = 'POINT'
        bpy.ops.transform.translate()

        bpy.ops.object.mode_set(mode='OBJECT')
        for m,hair in enumerate(psys.particles):
            verts = strands[m]
            hair.location = verts[0]
            #print("H", m, len(verts))
            if len(verts) < len(hair.hair_keys):
                continue
            for n,v in enumerate(hair.hair_keys):
                v.co = verts[n]
                #print("  ", n, verts[n], v.co)
                pass

        bpy.ops.object.mode_set(mode='OBJECT')

        if not useHairDynamics:
            psys.use_hair_dynamics = False
        else:
            psys.use_hair_dynamics = True
            cset = psys.cloth.settings
            cset.pin_stiffness = 1.0
            cset.mass = 0.05
            deflector = findDeflector(hum)


# ---------------------------------------------------------------------
#   Hair settings
# ---------------------------------------------------------------------

def updateHair(context):
    hum = context.object
    psys0 = hum.particle_systems.active
    psettings = getSettings(psys0.settings)
    hdyn0 = psys0.use_hair_dynamics
    csettings = getSettings(psys0.cloth.settings)
    for psys in hum.particle_systems:
        if psys == psys0:
            continue
        hum.particle_systems.active = psys
        setSettings(psys.settings, psettings)
        psys.use_hair_dynamics = hdyn0
        #setSettings(psys.cloth.settings, csettings)
    hum.particle_systems.active = psys0


def getSettings(pset):
    settings = {}
    for key in dir(pset):
        attr = getattr(pset, key)
        if (key[0] == "_" or
            key in ["count"]):
            continue
        if (
            isinstance(attr, int) or
            isinstance(attr, bool) or
            isinstance(attr, float) or
            isinstance(attr, str) or
            #attr is None or
            False
            ):
            settings[key] = attr
    return settings


def setSettings(pset, settings):
    for key,value in settings.items():
        try:
            setattr(pset, key, value)
        except AttributeError:
            pass


def colorHair(context):
    scn = context.scene
    hum = context.object
    mnames = []
    for psys in hum.particle_systems:
        pset = psys.settings
        mname = pset.material_slot
        if mname not in mnames:
            for mat in hum.data.materials:
                if mat.name == mname:
                    buildHairMaterial(mat, scn.DazHairColor, scn)
                    mnames.append(mname)
                    break
    toggleEditMode()


#------------------------------------------------------------------------
#   Deflector
#------------------------------------------------------------------------

def makeDeflector(pair, rig, bnames, cfg):
    _,ob = pair

    shiftToCenter(ob)
    if rig:
        for bname in bnames:
            if bname in cfg.bones.keys():
                bname = cfg.bones[bname]
            if bname in rig.pose.bones.keys():
                ob.parent = rig
                ob.parent_type = 'BONE'
                ob.parent_bone = bname
                pb = rig.pose.bones[bname]
                ob.matrix_basis = Mult2(pb.matrix.inverted(), ob.matrix_basis)
                ob.matrix_basis.col[3] -= Vector((0,pb.bone.length,0,0))
                break

    ob.draw_type = 'WIRE'
    ob.field.type = 'FORCE'
    ob.field.shape = 'SURFACE'
    ob.field.strength = 240.0
    ob.field.falloff_type = 'SPHERE'
    ob.field.z_direction = 'POSITIVE'
    ob.field.falloff_power = 2.0
    ob.field.use_max_distance = True
    ob.field.distance_max = 0.125*ob.DazScale


def shiftToCenter(ob):
    sum = Vector()
    for v in ob.data.vertices:
        sum += v.co
    offset = sum/len(ob.data.vertices)
    for v in ob.data.vertices:
        v.co -= offset
    ob.location = offset


def findDeflector(human):
    rig = human.parent
    if rig:
        children = rig.children
    else:
        children = human.children
    for ob in children:
        if ob.field.type == 'FORCE':
            return ob
    return None

#------------------------------------------------------------------------
#
#------------------------------------------------------------------------

class DAZ_OT_MakeHair(bpy.types.Operator):
    bl_idname = "daz.make_hair"
    bl_label = "Make Hair"
    bl_description = "Make particle hair from mesh hair"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH')

    def execute(self, context):
        try:
            makeHair(context)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}


class DAZ_OT_UpdateHair(bpy.types.Operator):
    bl_idname = "daz.update_hair"
    bl_label = "Update Hair"
    bl_description = "Change settings for particle hair"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH')

    def execute(self, context):
        try:
            updateHair(context)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}


class DAZ_OT_ColorHair(bpy.types.Operator):
    bl_idname = "daz.color_hair"
    bl_label = "Color Hair"
    bl_description = "Change particle hair color"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH')

    def execute(self, context):
        try:
            colorHair(context)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}

#------------------------------------------------------------------------
#   Connect
#------------------------------------------------------------------------

def connectHair(context):
    hum = context.object
    for mod in hum.modifiers:
        if isinstance(mod, bpy.types.ParticleSystemModifier):
            print(mod)

    nparticles = len(hum.particle_systems)
    for n in range(nparticles):
        hum.particle_systems.active_index = n
        print(hum.particle_systems.active_index, hum.particle_systems.active)
        bpy.ops.particle.particle_edit_toggle()
        bpy.ops.particle.disconnect_hair()
        bpy.ops.particle.particle_edit_toggle()
        bpy.ops.particle.connect_hair()
        bpy.ops.particle.particle_edit_toggle()


class DAZ_OT_ConnectHair(bpy.types.Operator):
    bl_idname = "daz.connect_hair"
    bl_label = "Connect Hair"
    bl_description = "(Re)connect hair"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH')

    def execute(self, context):
        connectHair(context)
        return{'FINISHED'}

#------------------------------------------------------------------------
#   Materials
#------------------------------------------------------------------------

def buildHairMaterial(mat, color, scn):
    if scn.render.engine in ['BLENDER_RENDER', 'BLENDER_GAME']:
        buildHairMaterialInternal(mat, list(color[0:3]))
    else:
        buildHairMaterialCycles(mat, list(color[0:3]))
    return mat

# ---------------------------------------------------------------------
#   Blender Internal
# ---------------------------------------------------------------------

def buildHairMaterialInternal(mat, rgb):
    mat.diffuse_color = rgb
    mat.diffuse_intensity = 0.1
    mat.specular_color = rgb

    mat.use_transparency = True
    mat.transparency_method = 'MASK'
    mat.alpha = 1.0
    mat.specular_alpha = 0.0

    mat.use_diffuse_ramp = True
    mat.diffuse_ramp_blend = 'MIX'
    mat.diffuse_ramp_factor = 1
    mat.diffuse_ramp_input = 'SHADER'

    mat.use_specular_ramp = True
    mat.specular_ramp_blend = 'MIX'
    mat.specular_ramp_factor = 1
    mat.specular_ramp_input = 'SHADER'

    defaultRamp(mat.diffuse_ramp, rgb)
    defaultRamp(mat.specular_ramp, rgb)

    mat.strand.root_size = 2
    mat.strand.tip_size = 1
    mat.strand.width_fade = 1
    return mat


def defaultRamp(ramp, rgb):
    ramp.interpolation = 'LINEAR'
    ramp.elements.new(0.1)
    ramp.elements.new(0.2)
    for n,data in enumerate([
        (0, rgb+[0]),
        (0.07, rgb+[1]),
        (0.6, rgb+[1]),
        (1.0, rgb+[0])
        ]):
        elt = ramp.elements[n]
        elt.position, elt.color = data

# ---------------------------------------------------------------------
#   Cycles
# ---------------------------------------------------------------------

class NodeTree:
    def __init__(self, tree):
        self.nodes = tree.nodes
        self.links = tree.links
        self.ycoords = 10*[500]

    def addNode(self, n, stype):
        node = self.nodes.new(type = stype)
        node.location = (n*250-500, self.ycoords[n])
        self.ycoords[n] -= 250
        return node

    def addTexImageNode(self, mhMat, texco, channel, cfg):
        try:
            filepath = mhMat[channel]
        except KeyError:
            return None
        tex = self.addNode(2, 'ShaderNodeTexImage')
        tex.image = loadImage(filepath, cfg)
        self.links.new(texco.outputs['UV'], tex.inputs['Vector'])
        return tex

def buildHairMaterialCycles(mat, rgb):
    print("Creating CYCLES HAIR material", mat.name)
    mat.use_nodes= True
    mat.node_tree.nodes.clear()
    tree = NodeTree(mat.node_tree)
    links = mat.node_tree.links

    info = tree.addNode(1, 'ShaderNodeHairInfo')

    val2rgb = tree.addNode(1, 'ShaderNodeValToRGB')
    links.new(info.outputs['Intercept'], val2rgb.inputs['Fac'])
    val2rgb.color = rgb
    defaultRamp(val2rgb.color_ramp, rgb)

    refl = tree.addNode(2, 'ShaderNodeBsdfHair')
    refl.component = 'Reflection'
    refl.inputs['Offset'].default_value = 0
    refl.inputs[2].default_value = 0.1
    refl.inputs[3].default_value = 1.0
    links.new(val2rgb.outputs['Color'], refl.inputs['Color'])

    trans = tree.addNode(2, 'ShaderNodeBsdfHair')
    trans.component = 'Transmission'
    trans.inputs['Offset'].default_value = 0
    trans.inputs[2].default_value = 0.1
    trans.inputs[3].default_value = 1.0
    links.new(val2rgb.outputs['Color'], trans.inputs['Color'])

    mix1 = tree.addNode(3, 'ShaderNodeMixShader')
    mix1.inputs[0].default_value = 0.3
    links.new(refl.outputs['BSDF'], mix1.inputs[1])
    links.new(trans.outputs['BSDF'], mix1.inputs[2])

    diffuse = tree.addNode(2, 'ShaderNodeBsdfDiffuse')
    diffuse.inputs["Roughness"].default_value = 0
    links.new(val2rgb.outputs['Color'], diffuse.inputs['Color'])

    mix2 = tree.addNode(3, 'ShaderNodeMixShader')
    mix2.inputs[0].default_value = 0.4
    links.new(mix1.outputs['Shader'], mix2.inputs[1])
    links.new(diffuse.outputs['BSDF'], mix2.inputs[2])

    aniso = tree.addNode(3, 'ShaderNodeBsdfAnisotropic')

    mix3 = tree.addNode(4, 'ShaderNodeMixShader')
    mix3.inputs[0].default_value = 0.05
    links.new(mix2.outputs['Shader'], mix3.inputs[1])
    links.new(aniso.outputs['BSDF'], mix3.inputs[2])

    output = tree.addNode(4, 'ShaderNodeOutputMaterial')
    links.new(mix3.outputs['Shader'], output.inputs['Surface'])

# ---------------------------------------------------------------------
#   Pinning
# ---------------------------------------------------------------------

def pinCoeffs(scn):
    x0 = scn.DazHairPinningX0
    x1 = scn.DazHairPinningX1
    w0 = scn.DazHairPinningW0
    w1 = scn.DazHairPinningW1
    k = (w1-w0)/(x1-x0)
    return x0,x1,w0,w1,k


def meshAddPinning(context):
    ob = context.object
    x0,x1,w0,w1,k = pinCoeffs(context.scene)

    if "HairPinning" in ob.vertex_groups.keys():
        vgrp = ob.vertex_groups["HairPinning"]
        ob.vertex_groups.remove(vgrp)

    vgrp = ob.vertex_groups.new(name="HairPinning")
    uvs = ob.data.uv_layers.active.data
    m = 0
    for f in ob.data.polygons:
        for n,vn in enumerate(f.vertices):
            x = 1-uvs[m+n].uv[1]
            if x < x0:  w = w0
            elif x > x1: w = w1
            else: w = w0 + k*(x-x0)
            vgrp.add([vn], w, 'REPLACE')
        m += len(f.vertices)


class DAZ_OT_MeshAddPinning(bpy.types.Operator):
    bl_idname = "daz.mesh_add_pinning"
    bl_label = "Add Pinning Group"
    bl_description = "Add HairPin group to mesh hair"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH')

    def execute(self, context):
        meshAddPinning(context)
        return{'FINISHED'}


def hairAddPinning(context):
    ob = context.object
    x0,x1,w0,w1,k = pinCoeffs(context.scene)


class DAZ_OT_HairAddPinning(bpy.types.Operator):
    bl_idname = "daz.hair_add_pinning"
    bl_label = "Hair Add Pinning"
    bl_description = "Add HairPin group to hair strands"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH')

    def execute(self, context):
        hairAddPinning(context)
        return{'FINISHED'}

# ---------------------------------------------------------------------
#   Initialize
# ---------------------------------------------------------------------

classes = [
    DAZ_OT_MakeHair,
    DAZ_OT_UpdateHair,
    DAZ_OT_ColorHair,
    DAZ_OT_ConnectHair,
    DAZ_OT_MeshAddPinning,
    DAZ_OT_HairAddPinning,
]

def initialize():
    bpy.types.Scene.DazHairColor = FloatVectorProperty(
        name = "Hair Color",
        subtype = "COLOR",
        size = 4,
        min = 0.0,
        max = 1.0,
        default = (0.5, 0.05, 0.1, 1)
    )

    bpy.types.Scene.DazHairSparsity = IntProperty(
        name = "Sparsity",
        min = 1,
        max = 50,
        default = 1,
        description = "Only use every n:th hair"
    )
    bpy.types.Scene.DazHairSize = IntProperty(
        name = "Hair Length",
        min = 5,
        max = 100,
        default = 20,
        description = "Hair length"
    )
    bpy.types.Scene.DazResizeHair = BoolProperty(
        name = "Resize Hair",
        default = False,
        description = "Resize hair afterwards"
    )
    bpy.types.Scene.DazResizeInBlocks = BoolProperty(
        name = "Resize In Blocks",
        default = False,
        description = "Resize hair in blocks of ten afterwards"
    )

    bpy.types.Scene.DazSkullGroup = EnumProperty(
        items = [('NONE', "None", "No Skull group"),
                 ('TOP', "Top", "Assign only top vertex to Skull group"),
                 ('ALL', "All", "Assign all vertices to Skull group"),
                 ],
        name = "Skull Group",
        description = "Vertex group to control hair density",
        default = 'TOP')

    bpy.types.Scene.DazHairPinningX0 = FloatProperty(
        name = "Pin X0",
        min = 0.0,
        max = 1.0,
        default = 0.25,
        precision = 3,
        description = ""
    )

    bpy.types.Scene.DazHairPinningX1 = FloatProperty(
        name = "Pin X1",
        min = 0.0,
        max = 1.0,
        default = 0.75,
        precision = 3,
        description = ""
    )

    bpy.types.Scene.DazHairPinningW0 = FloatProperty(
        name = "Pin W0",
        min = 0.0,
        max = 1.0,
        default = 1.0,
        precision = 3,
        description = ""
    )

    bpy.types.Scene.DazHairPinningW1 = FloatProperty(
        name = "Pin W1",
        min = 0.0,
        max = 1.0,
        default = 0.0,
        precision = 3,
        description = ""
    )

    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
