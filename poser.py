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
from collections import OrderedDict

from bpy_extras.io_utils import ImportHelper
from bpy.props import *
from mathutils import Vector, Euler
from .error import *
from .utils import *
from .transform import Transform
from .settings import theSettings
from .globvars import thePoserExtensions, thePoserUpcaseExtensions, thePoserDefaults, theImagedPoserDefaults
if bpy.app.version < (2,80,0):
    from .buttons27 import AffectOptions, ActionOptions, PoseLibOptions, ConvertOptions
    from .buttons27 import PoserFile, SingleFile, ScaleLock
else:
    from .buttons28 import AffectOptions, ActionOptions, PoseLibOptions, ConvertOptions
    from .buttons28 import PoserFile, SingleFile, ScaleLock
from .animation import addToPoseLib
from .animation import FrameConverter

#-------------------------------------------------------------
#   Utilities
#-------------------------------------------------------------

def d2b(v):
    return theSettings.scale*Vector((float(v[0]), -float(v[2]), float(v[1])))

def d2bu(v):
    return Vector((float(v[0]), -float(v[2]), float(v[1])))

def duv(v):
    return Vector((float(v[0]), float(v[1])))


def shortName(string):
    string = string.replace(":","/")
    return os.path.splitext(os.path.basename(string))[0]

#-------------------------------------------------------------
#
#-------------------------------------------------------------

def loadPoserFiles(filepaths, context):
    scn = context.scene
    startframe = scn.frame_current
    for filepath in filepaths:
        print("*", os.path.basename(filepath), scn.frame_current)
        loadPoserFile(filepath, context)
        scn.frame_current += 1
    scn.frame_current = startframe


def includePoserFile(file):
    fname,ext = os.path.splitext(file)
    return (ext[1:] in thePoserExtensions and
            (len(the.includes) == 0 or the.includes in file) and
            (len(the.excludes) == 0 or the.excludes not in file) )


def decodeAndLoad(filepath):
    import gzip
    from .fileutils import safeOpen
    try:
        with gzip.open(filepath, 'rb') as fp:
            bytes = fp.read()
    except IOError:
        bytes = None

    if bytes:
        string = bytes.decode("utf-8")
        return string.split("\n")
    else:
        try:
            fp = safeOpen(filepath, "rU")
            return tokenize(fp, False)
            lines = list(fp)
        except FileNotFoundError:
            raise DazError("File not found:\n%s" % filepath)
        finally:
            fp.close()
        return lines


def tokenize(fp, debug):
    from .fileutils import safeOpen
    stack = []
    tokens = []
    for line in fp:
        words = line.split()
        if words == []:
            continue
        elif words[0] == "{":
            stack.append(tokens)
            tokens = []
        elif words[0] == "}":
            ntokens = tokens
            tokens = stack[-1]
            if tokens:
                tokens[-1].extend(ntokens)
                stack = stack[:-1]
            else:
                tokens = ntokens
                break
        elif words[0] != "#":
            tokens.append(words)
    if debug:
        out = safeOpen("/home/test.txt", "w")
        printStack(tokens, "", out)
        out.close()
    return tokens


def printStack(tokens, prefix, fp):
    for token in tokens:
        fp.write("%s%s\n" % (prefix,token))
        continue

        if token == []:
            continue
        elif isinstance(token[0], list):
            printStack(token, prefix+"  ", fp)
        else:
            fp.write("%s%s\n" % (prefix, token))


def loadPoserFile(filepath, context):
    #print("\n----------- Loading", filepath)
    tokens = decodeAndLoad(filepath)
    scn = context.scene
    if the.useActive:
        rig = context.object
        if rig and rig.type == 'MESH':
            rig = rig.parent
    else:
        rig = None
    if rig and rig.type != 'ARMATURE':
        rig = None
    if rig and the.clearPose:
        clearPose(rig, scn)

    name = os.path.basename(filepath)
    pfile = PoserFile(name, filepath)
    pfile.parse(tokens)
    pfile.build(context, rig)


def clearPose(rig, scn):
    if the.affectObject:
        tfm = Transform()
        tfm.clearRna(rig)
        if the.insertKeys:
            tfm.insertKeys(rig, None, scn.frame_current, rig.name, [])

    for pb in rig.pose.bones:
        tfm = Transform()
        tfm.clearRna(pb)
        if the.insertKeys:
            tfm.insertKeys(rig, pb, scn.frame_current, pb.name, [])

#-------------------------------------------------------------
#   Poser
#-------------------------------------------------------------

class Poser:
    def __init__(self, id, filepath):
        self.filepath = tolower(filepath.replace("\\","/"))
        self.id = id
        self.name = id
        self.rna = None
        self.built = False
        self.special = []
        self.resources = {}


    def getName(self):
        words = self.name.rsplit(":")
        if len(words) > 1 and words[-1].isdigit():
            return words[-2]
        else:
            return words[-1].split(".",2)[0]


    def ignore(self):
        n = len("GetStringRes")
        return (self.name[0:n] == "GetStringRes")


    def getResource(self, tokens):
        path = " ".join(tokens)
        if path not in self.resources.keys():
            self.currentResource = self.resources[path] = Resource(path, self.filepath)
            self.currentResource.parse(tokens)
        else:
            self.currentResource = self.resources[path]
        print("Got resource", self.currentResource)


    def getAbsolutePath(self, relpath, preferred):
        relpath1 = tolower(relpath.replace(":","/"))
        if relpath1[0] == '"':
            relpath1 = relpath1[1:-1]
        if relpath1[0] == '/':
            relpath1 = relpath1[1:]
        #if relpath1[-4:] == ".bum":
        #    relpath1 = relpath1[:-4] + ".jpg"
        file = os.path.basename(relpath1)
        words = relpath1.split("/", 2)
        top = words[0]
        known = ["geometries", "textures", "libraries", "figures", "props", "poses"]
        type = match(known, self.filepath)
        folder2 = None
        if top == "runtime" and top in self.filepath:
            folder1 = self.filepath.split(top)[0]
        elif type:
            folder2 = self.filepath.rsplit(type,2)[0]
            folder1 = os.path.join(folder2, preferred)
        else:
            folder1 = os.path.dirname(self.filepath)
        path = os.path.join(folder1, relpath1)
        if os.path.exists(path):
            return path
        path = findInFolder(os.path.dirname(path), file)
        if not path:
            path = findInFolder(folder1, file)
        if not path and folder2:
            path = findInFolder(folder2, file)
        if not path:
            msg = "Did not find file:\n%s" % relpath
            print(msg)
            print("  RP", relpath1)
            n = len("getstringres")
            if relpath1[0:n] == "getstringres":
                return ""
            print("  FL", file)
            print("  PA", path)
            print("  F1", folder1)
            print("  F2", folder2)
            print("  PR", preferred)
            #raise DazError(msg)
            return ""
        return path


def findInFolder(folder, file):
    #print("FIF", folder)
    try:
        files = [tolower(f) for f in os.listdir(folder)]
    except FileNotFoundError:
        return None
    except PermissionError:
        print("Permission", file)
        halt
    fnames = dict([(os.path.splitext(f)[0], f) for f in files])
    if file in files:
        return os.path.join(folder, file)
    fname = os.path.splitext(file)[0]
    if fname in fnames.keys():
        return os.path.join(folder, fnames[fname])
    for file1 in files:
        path1 = os.path.join(folder, file1)
        if os.path.isdir(path1):
            path = findInFolder(path1, file)
            if path:
                return path
    return None

#-------------------------------------------------------------
#   PoserFile
#-------------------------------------------------------------

class PoserFile(Poser, FrameConverter):
    def __init__(self, id, filepath):
        Poser.__init__(self, id, filepath)
        self.actors = OrderedDict()
        self.props = OrderedDict()
        self.currentResource = None
        self.controlProps = {}
        self.figures = {}
        self.special = ["actor", "controlProp", "figure", "prop", "figureResFile"]

    def __repr__(self):
        return ("<PoserFile %s>" % (self.id))

    def parse(self, tokens):
        for token in tokens:
            key = token[0]
            if key == "actor":
                id = token[1]
                if id not in self.actors.keys():
                    self.actors[id] = Actor(id, self.filepath)
                actor = self.actors[id]
                if actor.geom:
                    actor.resource = self.currentResource
                actor.parse(token[2:])
            elif key == "controlProp":
                id = token[1]
                if id not in self.controlProps.keys():
                    self.controlProps[id] = ControlProp(id, self.filepath)
                self.controlProps[id].parse(token[2:])
            elif key == "figure":
                id = "Figure"
                if id not in self.figures.keys():
                    self.figures[id] = Figure(id, self.filepath)
                self.figures[id].parse(token[1:])
            elif key == "prop":
                id = token[1]
                if id not in self.props.keys():
                    self.props[id] = Prop(id, self.filepath)
                self.props[id].parse(token[2:])
            elif key == "figureResFile":
                self.getResource(token[1:])


    def build(self, context, rig):
        #print("Building file", the.useActive)
        scn = context.scene

        if the.useActive:
            actors = [actor.getName() for actor in self.actors.values()]
            conv,twists,bonemap = self.getConv(actors, rig)
            locks = self.getLocks(rig, conv)

            frames = self.getFrames(rig, conv, twists, bonemap)
            if the.convertPoses:
                frames = self.convertAnimations(frames, rig, conv, bonemap)
            self.buildFrames(frames, scn, rig)

        else:
            for prop in self.props.values():
                prop.build(context, None)
                transes = prop.getTranslate()
                rots = prop.getRotate()
                ob = prop.rna
                buildTransform(scn, ob, ob, transes, rots)
            for figure in self.figures.values():
                figure.build(context, self)
            for res in self.resources.values():
                res.build(context, None)
            for actor in self.actors.values():
                actor.build(context, None)
        #print("Built", self.filepath)


    def convertAnimations(self, frames, rig, conv, bonemap):
        from .convert import getConverter, getCharacter
        from .figure import getRigType

        trgCharacter = getCharacter(rig)
        if trgCharacter is None:
            return
        restmats = {}
        nrestmats = {}
        transmats = {}
        ntransmats = {}
        xyzs = {}
        nxyzs = {}
        parents = dict([(bone.name, bone.parent.name) for bone in rig.data.bones if bone.parent])
        for bname,nname in bonemap.items():
            self.getMatrices(bname, None, the.srcCharacter, parents, restmats, transmats, xyzs)
            self.getMatrices(nname, rig, trgCharacter, parents, nrestmats, ntransmats, nxyzs)
        nframes = []
        for t,struct in frames:
            nstruct = {}
            nframes.append((t,nstruct))
            for bname,nname in bonemap.items():
                if nname in struct.keys() and nname in ntransmats.keys() and bname in transmats.keys():
                    nstruct[nname] = self.convertFrame(ntransmats[nname].inverted(), transmats[bname], xyzs[bname], nxyzs[nname], struct[nname])
        return nframes


    def convertFrame(self, amat, bmat, xyz, nxyz, frame):
        trans,rot = frame
        if rot is None:
            return frame
        mat = Euler(Vector(rot)*D, xyz).to_matrix()
        nmat = amat * mat * bmat
        nrot = Vector(nmat.to_euler(nxyz))/D
        return trans,nrot


    def getFrames(self, rig, conv, twists, bonemap):
        frames = {}
        for actor in self.actors.values():
            bname,transes,rots = actor.getTransforms(conv, bonemap)
            if not (
                bname in rig.pose.bones.keys() or
                (bname == "BODY" and the.affectObject)):
                #print("Missing bone:", actor.getName(), bname)
                continue

            for t,trans in transes.items():
                if t not in frames.keys():
                    frames[t] = {bname: [trans,None]}
                elif bname not in frames[t].keys():
                    frames[t][bname] = [trans,None]
                else:
                    frames[t][bname][0] = trans
            for t,rot in rots.items():
                if t not in frames.keys():
                    frames[t] = {bname: [None,rot]}
                elif bname not in frames[t].keys():
                    frames[t][bname] = [None,rot]
                else:
                    frames[t][bname][1] = rot

        '''
        bname = "thigh.fk.R"
        for t in frames.keys():
            if bname in frames[t].keys():
                print(t, frames[t][bname])
            else:
                print(t, "-")
        '''
        frames = list(frames.items())
        frames.sort()
        return frames


    def buildFrames(self, frames, scn, rig):
        from .node import setBoneTransform

        currframe = scn.frame_current
        for t,data in frames:
            scn.frame_current = currframe + t
            #if t % 50 == 0:
            #    print("Frame", t)
            for bname in data.keys():
                trans,rot = data[bname]
                tfm = Transform(trans=trans, rot=rot)
                if bname == "BODY":
                    tfm.setRna(rig)
                    if the.insertKeys:
                        tfm.insertKeys(rig, None, scn.frame_current, rig.name, [])
                    clearLocks(rig, False)
                elif bname in rig.pose.bones.keys():
                    pb = rig.pose.bones[bname]
                    setBoneTransform(tfm, pb)
                    pb.location = (0,0,0)
                    clearLocks(pb, True)
                    if the.insertKeys:
                        tfm.insertKeys(rig, pb, scn.frame_current, bname, [])

            if the.usePoseLib:
                name = os.path.splitext(os.path.basename(self.filepath))[0]
                addToPoseLib(rig, name)

        scn.frame_current = currframe

#-------------------------------------------------------------
#   Node
#-------------------------------------------------------------

class Node(Poser):
    def __init__(self, id, filepath):
        Poser.__init__(self, id, filepath)
        self.type = "Node"
        self.parent = None
        self.special = ["channels"]
        self.materials = {}
        self.targets = {}
        self.static = False
        self.channels = {}
        self.keyframes = {}
        self.group = None

    def __repr__(self):
        return ("<%s %s>" % (self.type, self.id))


    def addToGroup(self, ob):
        if not theSettings.group or bpy.app.version > (2,80,0):
            return
        if self.group is None:
            gname = os.path.splitext(os.path.basename(self.filepath))[0]
            self.group = bpy.data.groups.new(gname)
        self.group.objects.link(ob)


    def parse(self, tokens):
        for token in tokens:
            key = token[0]
            if key == "channels":
                return self.parseChannels(tokens[1:])


    def parseChannels(self, tokens):
        for token in tokens:
            key = token[0]
            if key == "targetGeom":
                name = token[1]
                if name not in self.targets.keys():
                    self.targets[name] = TargetGeom(name)
                #print("TGM", name, self)
                self.targets[name].parse(token[2:])
            elif len(token) <= 2:
                pass
            elif token[2][0] == "keys":
                self.keyframes[key] = token[2][1:]
            else:
                channel = self.channels[key] = {}
                for words in token[2:]:
                    channel[words[0]] = words[1:]


    def getOffset(self):
        channels = ["xOffsetA", "yOffsetA", "zOffsetA"]
        return [self.parseStatic(channel, 0.0) for channel in channels]


    def getTranslate(self):
        channels = ["translateX", "translateY", "translateZ"]
        frames = OrderedDict()
        for idx,channel in enumerate(channels):
            self.parseKeys(channel, idx, 0.0, frames)
        return frames


    def getRotate(self):
        channels = ["rotateX", "rotateY", "rotateZ"]
        frames = OrderedDict()
        for idx,channel in enumerate(channels):
            self.parseKeys(channel, idx, 0.0, frames)
        return frames


    def getScale(self):
        channels = ["scaleX", "scaleY", "scaleZ"]
        frames = OrderedDict()
        for idx,channel in enumerate(channels):
            self.parseKeys(channel, idx, 1.0, frames)
        return frames


    def getTranslateLimits(self):
        return self.getLimits(["translateX", "translateY", "translateZ"], theSettings.scale, True)


    def getRotateLimits(self):
        return self.getLimits(["rotateX", "rotateY", "rotateZ"], D, True)


    def getScaleLimits(self):
        return self.getLimits(["scaleX", "scaleY", "scaleZ"], 1.0, False)


    def getLimits(self, channels, scale, sign):
        MAX = 1e6
        mins = [-MAX,-MAX,-MAX]
        maxs = [MAX,MAX,MAX]
        for idx,channel in enumerate(channels):
            if channel not in self.channels.keys():
                continue
            if "min" in self.channels[channel]:
                string = self.channels[channel]["min"][0]
                min = float(string)*scale
                if sign and idx == 2:
                    maxs[idx] = -min
                else:
                    mins[idx] = min
            if "max" in self.channels[channel]:
                string = self.channels[channel]["max"][0]
                max = float(string)*scale
                if sign and idx == 2:
                    mins[idx] = -max
                else:
                    maxs[idx] = max
        return mins,maxs


    def parseStatic(self, channel, default):
        if channel not in self.channels.keys():
            return default
        for token in self.channels[channel]:
            if token[0] == "staticValue":
                return float(line[1])
        return default


    def parseKeys(self, channel, idx, default, frames):
        if channel not in self.keyframes.keys():
            return
        for token in self.keyframes[channel]:
            if token[0] == "k":
                t = int(token[1])
                if t not in frames.keys():
                    frames[t] = [default,default,default]
                frames[t][idx] = float(token[2])


    def parseMaterial(self, tokens):
        name = tokens[0]
        if name not in self.materials.keys():
            self.materials[name] = Material(name, self.filepath)
        return self.materials[name].parse(tokens[1:])


    def buildMaterials(self):
        mats = {}
        if "Preview" in self.materials.keys():
            del self.materials["Preview"]
        for mat in self.materials.values():
            mat.build()
            mats[mat.name] = mat.rna
        return mats

#-------------------------------------------------------------
#   Prop
#-------------------------------------------------------------

class Prop(Node):
    def __init__(self, id, filepath):
        Node.__init__(self, id, filepath)
        self.type = "Prop"
        self.special = ["geomCustom", "channels", "material", "objFileGeom"]
        self.verts = []
        self.faces = []
        self.uvs = []
        self.uvfaces = []
        self.normals = []
        self.numbVerts = 0
        self.numbTVerts = 0
        self.numbNVerts = 0
        self.numbTSets = 0
        self.numbElems = 0
        self.numbSets = 0
        self.usemtl = {}
        self.fgroups = {}
        self.vgroups = {}


    def parse(self, tokens):
        for token in tokens:
            key = token[0]
            if key == "geomCustom":
                self.parseGeomCustom(token[1:])
            elif key == "channels":
                self.parseChannels(token[1:])
            elif key == "material":
                self.parseMaterial(token[1:])
            elif key == "objFileGeom":
                self.getResource(token[3:])


    def parseGeomCustom(self, tokens):
        n = -1
        for token in tokens:
            key = token[0]
            n += 1
            if key in ["numbVerts", "numbTVerts", "numbNVerts", "numbTSets", "numbElems", "numbSets"]:
                setattr(self, key, int(token[1]))
            elif key in ["usemtl", "v", "g"]:
                break
        self.parseObjFile(tokens[n:])


    def parseObjFile(self, lines):
        vlines = [(n,line) for n,line in enumerate(lines) if line[0] == "v"]
        vtlines = [(n,line) for n,line in enumerate(lines) if line[0] == "vt"]
        vnlines = [(n,line) for n,line in enumerate(lines) if line[0] == "vn"]
        flines = [(n,line) for n,line in enumerate(lines) if line[0] == "f"]

        vblock = []
        vtblock = []
        vnblock = []
        fblock = []
        nf = flines[0][0]
        while (vlines[-1][0] > nf):
            vlines1 = [line for line in vlines if line[0] < nf]
            vblock.extend(vlines1)
            vtlines1 = [line for line in vtlines if line[0] < nf]
            vtblock.extend(vtlines1)
            vnlines1 = [line for line in vnlines if line[0] < nf]
            vnblock.extend(vnlines1)
            vlines = [line for line in vlines if line[0] > nf]
            vtlines = [line for line in vtlines if line[0] > nf]
            vnlines = [line for line in vnlines if line[0] > nf]
            nv = vlines[0][0]
            flines1 = [line for line in flines if line[0] < nv]
            fblock.extend(flines1)
            flines = [line for line in flines if line[0] > nv]
            nf = flines[0][0]
        vblock.extend(vlines)
        vtblock.extend(vtlines)
        vnblock.extend(vnlines)
        fblock.extend(flines)

        self.verts = [d2b(words[1:4]) for _,words in vblock]
        self.uvs = [duv(words[1:3]) for _,words in vtblock]
        #self.normals = [d2b(words[1:4]) for _,words in vnblock]

        self.faces = [[(int(word.split("/")[0])-1) for word in line[1:]]
                    for _,line in fblock]
        self.uvfaces = [[getUv(word) for word in line[1:]]
                    for _,line in fblock]

        usemtl = [(ln,line[1]) for ln,line in enumerate(lines) if line[0] == "usemtl"]
        fn0 = 0
        self.usemtl = {}
        while usemtl:
            mname = usemtl[0][1]
            if mname not in self.usemtl.keys():
                self.usemtl[mname] = []
            if len(usemtl) > 1:
                ln = usemtl[1][0]
            else:
                ln = fblock[-1][0] + 1
            mfaces = [fn0+n for n,face in enumerate(fblock[fn0:]) if face[0] < ln]
            self.usemtl[mname] += mfaces
            fn0 += len(mfaces)
            usemtl = usemtl[1:]

        groups = [(n,line) for n,line in enumerate(lines) if line[0] == "g"]
        fn0 = 0
        self.fgroups = {}
        while groups:
            line = groups[0][1]
            grps = []
            for gname in line[1:]:
                if gname not in self.fgroups.keys():
                    self.fgroups[gname] = []
                grps.append(self.fgroups[gname])
            if len(groups) > 1:
                ln = groups[1][0]
            else:
                ln = fblock[-1][0] + 1
            gfaces = [fn0+n for n,face in enumerate(fblock[fn0:]) if face[0] < ln]
            for grp in grps:
                grp.extend(gfaces)
            fn0 += len(gfaces)
            groups = groups[1:]

        self.vgroups = {}
        for gname,fgroup in self.fgroups.items():
            taken = dict([(vn,False) for vn in range(len(self.verts))])
            for fn in fgroup:
                for vn in self.faces[fn]:
                    taken[vn] = True
            self.vgroups[gname] = vgroup = [vn for vn in taken.keys() if taken[vn]]
            vgroup.sort()


    def build(self, context, figure):
        if self.built:
            return
        if self.resources:
            for res in self.resources.values():
                res.build(context, figure)
                self.rna = res.rna
            self.built = True
            return

        coll = getCollection(context)
        name = self.getName()
        print("BPROP", self, name)
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.verts, [], self.faces)
        ob = self.rna = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        setActiveObject(context, ob)
        self.addToGroup(ob)

        self.assignMaterials(me, figure)
        if self.uvfaces:
            self.buildUvTex(me)
        for target in self.targets.values():
            target.build(self.rna, None, None)

        if figure:
            activateObject(context, ob)
            rig = figure.rna
            mod = ob.modifiers.new(rig.name, 'ARMATURE')
            mod.object = rig
            ob.parent = rig
            if the.lockMeshes:
                ob.lock_location = (True,True,True)
                ob.lock_rotation = (True,True,True)
                ob.lock_scale = (True,True,True)

        self.built = True


    def assignMaterials(self, me, figure):
        if figure:
            mats = figure.buildMaterials()
        else:
            mats = self.buildMaterials()

        mlist = []
        mn = 0
        for mname,fnums in self.usemtl.items():
            try:
                mlist.append((mn, mats[mname], fnums))
                mn += 1
            except KeyError:
                print("Missing material:", mname)
                pass

        for mn,mat,fnums in mlist:
            me.materials.append(mat)
        for mn,mat,fnums in mlist:
            for fn in fnums:
                f = me.polygons[fn]
                f.material_index = mn
                f.use_smooth = True


    def buildUvTex(self, me):
        from .geometry import makeNewUvloop
        uvloop = makeNewUvloop(me, self.getName(), True)

        m = 0
        vnmax = len(self.uvs)
        for f in me.polygons:
            for n in range(len(f.vertices)):
                vn = self.uvfaces[f.index][n]
                if vn < vnmax:
                    uv = self.uvs[vn]
                    uvloop.data[m].uv = uv
                m += 1


def buildTransform(scn, ob, rna, transes, rots):
    tfm = Transform()
    if transes:
        tfm.setTrans(transes[0])
    if rots:
        tfm.setRot(rots[0])
    tfm.setRna(rna)
    if the.insertKeys:
        tfm.insertKeys(ob, rna, scn.frame_current, rna.name, [])


def getUv(string):
    words = string.split("/")
    return (int(words[1])-1 if len(words) > 1 else 0)

#-------------------------------------------------------------
#   Resource
#-------------------------------------------------------------

class Resource(Prop):
    def __init__(self, id, filepath):
        Prop.__init__(self, id, filepath)
        self.loaded = False


    def parse(self, tokens):
        if self.loaded:
            return

        self.loaded = True
        filepath = self.getAbsolutePath(self.name, "geometries")
        print("\nResource", self.name)
        print(filepath)
        ext = os.path.splitext(filepath)[1]
        if ext in [".obj", ".obz"]:
            tokens = decodeAndLoad(filepath)
        else:
            msg = ("Not an obj file:\n%s" % filepath)
            print(msg)
            return
            raise DazError(msg)

        self.parseObjFile(tokens)


    def build(self, context, figure):
        if self.built:
            return
        Prop.build(self, context, figure)

#-------------------------------------------------------------
#   Actor
#-------------------------------------------------------------

class Actor(Prop):
    def __init__(self, id, filepath):
        Prop.__init__(self, id, filepath)
        self.type = "Actor"
        self.figure = None
        self.origin = Vector((0,0,0))
        self.endPoint = Vector((0,0,1))
        self.resource = None
        self.geom = None
        self.special = [
            "geomCustom", "channels", "origin", "endPoint",
            "parent", "geomHandlerGeom"]


    def __repr__(self):
        return ("<Actor %s %s %s %s>" % (self.id, self.getName(), self.geom, self.parent))


    def getName(self):
        if self.geom:
            return self.geom
        else:
            return Prop.getName(self)


    def parse(self, tokens):
        for token in tokens:
            key = token[0]
            if key == "geomCustom":
                self.parseGeomCustom(token[1:])
            elif key == "channels":
                self.parseChannels(token[1:])
            elif key == "origin":
                self.origin = d2b(token[1:4])
            elif key == "endPoint":
                self.endPoint = d2b(token[1:4])
            elif key == "parent":
                if token[1] != "UNIVERSE":
                    self.parent = token[1]
            elif key == "geomHandlerGeom":
                self.geom = token[2]


    def build(self, context, figure):
        if self.built:
            return

        print("BACT", self.name)
        vgroup = None
        if self.resource:
            self.resource.build(context, figure)
            self.rna = self.resource.rna
            if self.geom in self.resource.vgroups.keys():
                vgroup = self.resource.vgroups[self.geom]
            elif self.geom[0:4] == "BODY":
                pass
            else:
                print("Missing vgroup", self)
        elif self.verts:
            Prop.build(self, context, figure)
            if self.geom in self.vgroups.keys():
                vgroup = self.vgroups[self.geom]

        ob = self.rna
        if ob is None:
            self.built = True
            return
        elif vgroup:
            vgrp = ob.vertex_groups.new(name=self.geom)
            for vn in vgroup:
                vgrp.add([vn], 1.0, 'REPLACE')
        elif figure:
            rig = figure.rna
            name = self.getName()
            if rig and name in rig.data.bones.keys():
                from .node import setParent
                bone = rig.data.bones[name]
                setParent(context, ob, rig, bone.name)

        for target in self.targets.values():
            target.build(ob, self.geom, vgroup)
        self.built = True


    def getTransforms(self, conv, bonemap):
        bname = self.getName()
        if bname in conv.keys():
            bonemap[bname] = conv[bname]
            bname = conv[bname]
        transes = self.getTranslate()
        rots = self.getRotate()
        return bname, transes, rots



def clearLocks(pb, useQuat):
    for idx in range(3):
        if pb.lock_location[idx]:
            pb.location[idx] = 0.0
        if pb.lock_rotation[idx]:
            pb.rotation_euler[idx] = 0.0
            if useQuat:
                pb.rotation_quaternion[idx] = 0.0

#-------------------------------------------------------------
#   Figure
#-------------------------------------------------------------

class Figure(Node):
    def __init__(self, id, filepath):
        Node.__init__(self, id, filepath)
        self.type = "Figure"
        self.special = ["channels", "material"]
        self.children = []


    def parse(self, tokens):
        for token in tokens:
            key = token[0]
            if key == "name":
                self.name = token[1]
            elif key == "channels":
                self.parseChannels(token[1:])
            elif key == "material":
                self.parseMaterial(token[1:])


    def build(self, context, file):
        if self.built:
            return
        eps = 1e-4*theSettings.scale

        coll = getCollection(context)
        name = self.getName()
        print("BFIG", self, name)
        amt = bpy.data.armatures.new(name)
        rig = self.rna = bpy.data.objects.new(name, amt)
        setattr(amt, DrawType, 'STICK')
        setattr(rig, ShowXRay, True)
        coll.objects.link(rig)
        setActiveObject(context, rig)
        self.addToGroup(rig)

        bpy.ops.object.mode_set(mode='EDIT')
        for actor in file.actors.values():
            if not actor.ignore():
                eb = amt.edit_bones.new(actor.getName())
                eb.head = actor.origin
                if (actor.endPoint - actor.origin).length < eps:
                    eb.tail = eb.head + Vector((0,0,eps))
                else:
                    eb.tail = actor.endPoint

        for actor in file.actors.values():
            if not actor.ignore():
                eb = amt.edit_bones[actor.getName()]
                if actor.parent:
                    if actor.parent not in file.actors.keys():
                        print("PAR", actor, actor.parent)
                        for name,actor in file.actors.items():
                            print("  ", name, actor)
                    parent = file.actors[actor.parent]
                    pname = parent.getName()
                    if pname in amt.edit_bones.keys():
                        eb.parent = amt.edit_bones[pname]
                        if (eb.parent and
                            (eb.parent.tail - eb.head).length < eps):
                            eb.use_connect = True

        bpy.ops.object.mode_set(mode='POSE')
        for pb in rig.pose.bones:
            pb.rotation_mode = 'XYZ'

        bpy.ops.object.mode_set(mode='OBJECT')
        for actor in file.actors.values():
            if not actor.ignore():
                actor.build(context, self)

        for actor in file.actors.values():
            if not actor.ignore():
                bname,transes,rots = actor.getTransforms({}, {})
                if bname in rig.pose.bones:
                    rna = rig.pose.bones[bname]
                else:
                    rna = rig
                buildTransform(context, rig, rna, transes, rots)

        self.built = True


def setLimits(pb, lock, cnstype, limits):
    cns = None
    print(pb, cnstype)
    print("  ", limits)
    for idx,limits in enumerate(limits):
        min,max = limits
        if min is None or max is None:
            continue
        elif min == max:
            lock[idx] = True
        else:
            if cns is None:
                cns = pb.constraints.new(cnstype)

#-------------------------------------------------------------
#   ControlProp
#-------------------------------------------------------------

class ControlProp(Node):
    def __init__(self, id, filepath):
        Node.__init__(self, id, filepath)
        self.type = "ControlProp"

#-------------------------------------------------------------
#   TargetGeom
#-------------------------------------------------------------

class TargetGeom(Poser):
    def __init__(self, id):
        Poser.__init__(self, id, "")
        self.special = ["indexes", "numbDeltas", "deltas"]
        self.deltas = []
        self.indexes = 0
        self.numbDeltas = 0
        self.rna = None

    def __repr__(self):
        return ("<TargetGeom %s>" % (self.id))


    def parse(self, tokens):
        for token in tokens:
            key = token[0]
            if key == "indexes":
                self.indexes = int(token[1])
            elif key == "numbDeltas":
                self.numbDeltas = int(token[1])
            elif key == "deltas":
                self.deltas = [(int(words[1]), d2b(words[2:5]))
                        for words in token[1:self.indexes+1]
                        if words[0] == "d"]


    def build(self, ob, geom, vgroup):
        if self.built or ob is None:
            return

        if vgroup is None:
            print("No vgroup")
            vgroup = list(range(len(ob.data.vertices)))

        if self.numbDeltas != len(vgroup):
            print("Vertex number mismatch: %d != %d" % (self.numbDeltas, len(vgroup)))
            print("Object: %s Geom: %s Target: %s" % (ob.name, geom, self.name))
            return

        if not ob.data.shape_keys:
            basic = ob.shape_key_add(name="Basic")
        else:
            basic = ob.data.shape_keys.key_blocks[0]
        name = self.getName()
        skey = self.rna = ob.shape_key_add(name=name)
        skey.slider_min = theSettings.propMin
        skey.slider_max = theSettings.propMax
        for v in ob.data.vertices:
            skey.data[v.index].co = v.co
        for delta in self.deltas:
            vn = vgroup[delta[0]]
            skey.data[vn].co += delta[1]
        self.built = True

#-------------------------------------------------------------
#   Material
#-------------------------------------------------------------

class Material(Poser):
    def __init__(self, id, filepath):
        Poser.__init__(self, id, filepath)
        self.special = [
            "KdColor", "KaColor", "KsColor",
            "bumpStrength",
            "textureMap", "bumpMap", "reflectionMap", "transparencyMap",
            "shaderTree",
        ]
        self.KdColor = (0,0,0,0)
        self.KaColor = (0,0,0,0)
        self.KsColor = (0,0,0,0)
        self.bumpStrength = 0.0
        self.reflectionStrength = 0.0
        self.NsExponent = 80
        self.textureMap = None
        self.bumpMap = None
        self.reflectionMap = None
        self.transparencyMap = None


    def __repr__(self):
        return ("<Material %s>" % (self.id))


    def parse(self, tokens):
        for token in tokens:
            key = token[0]
            if key in ["KdColor", "KaColor", "KsColor"]:
                setattr(self, key, (float(token[1]), float(token[2]), float(token[3]), float(token[4])))
            elif key in ["bumpStrength", "reflectionStrength", "NsExponent"]:
                setattr(self, key, float(token[1]))
            elif key in ["textureMap", "bumpMap", "reflectionMap", "transparencyMap"]:
                if token[1].upper() == "NO_MAP":
                    setattr(self, key, None)
                else:
                    setattr(self, key, " ".join(token[1:]))


    def build(self):
        if self.built:
            return self.rna
        name = self.getName()
        mat = self.rna = bpy.data.materials.new(name)
        mat.diffuse_color[0:3] = self.KdColor[0:3]
        mat.alpha = self.KdColor[3]
        mat.specular_color = self.KsColor[0:3]
        mat.specular_intensity = 0.1
        mat.specular_hardness = (1-self.NsExponent/100)*512
        mat.specular_alpha = self.KsColor[3]
        if self.textureMap:
            mtex,img = self.addImageTexture(mat, self.textureMap, "Diffuse")
            mtex.use_map_color_diffuse = True
            if (not self.transparencyMap and
                img and
                img.channels == 4 and
                img.use_alpha):
                mtex.use_map_alpha = True
                mat.use_transparency = True
                mat.alpha = 0.0
                mat.specular_alpha = 0.0
        if self.bumpMap:
            mtex,img = self.addImageTexture(mat, self.bumpMap, "Bump")
            mtex.use_map_normal = True
            mtex.normal_factor = self.bumpStrength
            mtex.use_rgb_to_intensity = True
            mtex.bump_method = 'BUMP_ORIGINAL'
            #mtex.bump_method = 'BUMP_BEST_QUALITY'
        if self.reflectionMap:
            mtex,img = self.addImageTexture(mat, self.reflectionMap, "Reflect")
            mtex.use_map_mirror = True
            mtex.mirror_factor = self.reflectionStrength
            mirror = mat.raytrace_mirror
            #mirror.use = True
            mirror.reflect_factor = self.reflectionStrength
        if self.transparencyMap:
            mtex,img = self.addImageTexture(mat, self.transparencyMap, "Transpar")
            mtex.use_map_alpha = True
            mat.use_transparency = True
            mat.alpha = 0.0
            mat.specular_alpha = 0.0
        self.built = True
        return mat


    def addImageTexture(self, mat, relpath, channel):
        if relpath in the.images.keys():
            img,name = the.images[relpath]
        else:
            imgpath = self.getAbsolutePath(relpath, "textures")
            name = shortName(relpath)
            try:
                img = bpy.data.images.load(imgpath)
                img.name = name
            except RuntimeError:
                print("Could not open", imgpath)
                img = None
            the.images[relpath] = img,name

        key = relpath+channel
        if mat.name in the.materials.keys():
            mtexs = the.materials[mat.name]
            if key in mtexs:
                return mtexs[key],img
        else:
            mtexs = the.materials[mat.name] = {}

        if key in the.textures.keys():
            tex = the.textures[key]
        else:
            tex = bpy.data.textures.new(name, 'IMAGE')
            tex.image = img
            the.textures[key] = tex

        mtex = mat.texture_slots.add()
        mtex.texture = tex
        mtex.use_map_color_diffuse = False
        mtex.texture_coords = 'UV'
        mtexs[key] = mtex
        return mtex,img

#-------------------------------------------------------------
#   Buttons
#-------------------------------------------------------------

class The:
    def __init__(self, btn, scn, useActive):
        theSettings.reset(scn)
        theSettings.scale = btn.unitScale * 254
        self.useActive = useActive
        self.convertPoses = btn.convertPoses
        self.clearPose = btn.useClearPose
        self.affectObject = btn.affectObject
        self.lockMeshes = btn.lockMeshes
        if scn.tool_settings.use_keyframe_insert_auto:
            self.insertKeys = True
        else:
            self.insertKeys = btn.useAction
        self.srcCharacter = btn.srcCharacter
        if btn.useAction:
            self.makeNewAction = btn.makeNewAction
        self.usePoseLib = btn.usePoseLib
        if btn.usePoseLib:
            self.makeNewPoseLib = btn.makeNewPoseLib
        self.images = {}
        self.textures = {}
        self.materials = {}


def loadPoserAnimation(self, context, filepaths):
    from .animation import clearAction, nameAction, selectAll
    global the
    scn = context.scene
    rig = context.object
    self.unitScale = rig.DazScale
    the = The(self, scn, True)
    if not self.selectedOnly:
        selected = selectAll(rig, True)
    clearAction(self, rig)
    loadPoserFiles(filepaths, context)
    nameAction(self, rig, scn)
    if not self.selectedOnly:
        selectAll(rig, selected)


class PoserBase(PoserFile, SingleFile):
    zup = "Poser"
    fitMeshes = 'UNIQUE'

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


    def getPoserFilePath(self):
        from .fileutils import getFilePath
        return getFilePath(self.filepath, thePoserExtensions)


class DAZ_OT_LoadAssets(bpy.types.Operator, PoserBase, ScaleLock):
    bl_idname = "daz.import_poser"
    bl_label = "Import Poser File"
    bl_description = "Import a native DAZ file (%s)" % thePoserDefaults
    bl_options = {'UNDO'}

    useClearPose = False
    affectObject = True
    convertPoses = False
    insertKeys = False
    usePoseLib = False
    useTranslations = True
    useRotations = True
    useScale = True
    useGeneral = True
    makeNewAction = False
    actionName = ""

    def draw(self, context):
        self.layout.prop(self, "unitScale")
        self.layout.prop(self, "lockMeshes")


    def execute(self, context):
        global the
        try:
            the = The(self, context.scene, False)
            filepath = self.getPoserFilePath()
            loadPoserFiles(filepath, context)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DAZ_OT_LoadAssets,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
