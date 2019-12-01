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
import os
import copy
from collections import OrderedDict

from .asset import Asset
from .utils import *
from .settings import theSettings
from .error import *
from mathutils import Vector, Matrix
if bpy.app.version < (2,80,0):
    from .buttons27 import SlotString, UseInternalBool, ImageFile, DazImageFile, MultiFile, ResizeOptions, DazChannelFactor
else:
    from .buttons28 import SlotString, UseInternalBool, ImageFile, DazImageFile, MultiFile, ResizeOptions, DazChannelFactor

WHITE = Vector((1.0,1.0,1.0))
GREY = Vector((0.5,0.5,0.5))
BLACK = Vector((0.0,0.0,0.0))

#-------------------------------------------------------------
#   Materials
#-------------------------------------------------------------

def getMatKey(id):
    from .asset import normalizePath
    id = normalizePath(id)
    key = id.split("#")[-1]
    words = key.rsplit("-",1)
    if (len(words) == 2 and
        words[1].isdigit()):
        return words[0]
    else:
        return key


class Material(Asset):

    def __init__(self, fileref):
        Asset.__init__(self, fileref)
        self.scene = None
        self.shader = 'DAZ'
        self.channels = OrderedDict()
        self.studioChannels = OrderedDict()
        self.textures = OrderedDict()
        self.groups = []
        self.ignore = False
        self.shells = []
        self.geometry = None
        self.geosockets = []
        self.uv_set = None
        self.uv_sets = {}
        self.udim = 0
        self.basemix = 0
        self.thinWalled = False
        self.refractive = False
        self.thinGlass = False
        self.shareGlossy = False
        self.hideMaterial = False
        self.metallic = False
        self.dualLobeWeight = 0
        self.translucent = False


    def __repr__(self):
        return ("<Material %s %s %s>" % (self.id, self.rna, self.geometry))


    def parse(self, struct):
        Asset.parse(self, struct)
        if "url" in struct.keys():
            asset = self.getAsset(struct["url"])
            if asset:
                self.channels = copy.deepcopy(asset.channels)
        self.set(struct)


    def update(self, struct):
        Asset.update(self, struct)
        self.set(struct)
        #for grp in struct["groups"]:
        #    setMaterial(struct["geometry"], grp, self)
        if "uv_set" in struct.keys():
            from .geometry import Uvset
            self.uv_set = self.getTypedAsset(struct["uv_set"], Uvset)
            if self.uv_set:
                self.uv_set.material = self
        if "geometry" in struct.keys():
            geo = self.getAsset(struct["geometry"], True)
            key = getMatKey(self.id)
            if geo is not None:
                if key not in geo.materials.keys():
                    geo.materials[key] = []
                geo.materials[key].append(self)
                self.geometry = geo

        self.basemix = self.getValue(["Base Mixing"], 0)
        if self.basemix == 2:
            self.basemix = 0
        elif self.basemix not in [0,1]:
            raise DazError("Unknown Base Mixing: %s             " % self.material.basemix)

        self.thinWalled = self.getValue(["Thin Walled"], False)
        self.refractive = (self.getValue("getChannelRefractionStrength", 0) > 0.01 or
                           self.getValue("getChannelOpacity", 1) < 0.99)
        self.thinGlass = (self.thinWalled and self.refractive)
        self.shareGlossy = self.getValue(["Share Glossy Inputs"], False)
        self.metallic = (self.getValue(["Metallic Weight"], 0) > 0.5)
        self.dualLobeWeight = self.getValue(["Dual Lobe Specular Weight"], 0)
        self.translucent = (self.getValue("getChannelTranslucencyWeight", 0) > 0.01)


    def set(self, struct):
        for key,data in struct.items():
            if key == "extra":
                for extra in data:
                    self.setExtra(extra)
            elif isinstance(data, dict):
                if "channel" in data.keys():
                    self.replaceChannel(key, data["channel"])
                elif "color" in data.keys() or "strength" in data.keys():
                    self.replaceChannel(key, data)


    def setExtra(self, struct):
        if (struct["type"] == "studio_material_channels" and
            "channels" in struct.keys()):
            for elt in struct["channels"]:
                data = elt["channel"]
                key = data["id"]
                self.replaceChannel(key, data)
                if "label" in self.channels.keys():
                    key = data["label"]
                    self.replaceChannel(key, data)
        elif struct["type"] == "studio/material/uber_iray":
            self.shader = 'IRAY'
        elif struct["type"] == "studio/material/daz_brick":
            self.shader = '3DELIGHT'
        elif struct["type"] == "studio/material/daz_shader":
            self.shader = 'DAZ'
        return
        if struct["type"] == "studio/material/daz_shader":
            if "definition" in struct.keys():
                print("DEFINED IN", struct["definition"])
            elif "property_settings" in struct.keys():
                for prop,value in struct["property_settings"].items():
                    self.channels[prop] = value


    def replaceChannel(self, key, data):
        if key in self.channels.keys():
            channel = self.channels[key]
            for name,value in data.items():
                channel[name] = value
        else:
            self.channels[key] = data


    def copyChannels(self, base):
        for key,value in base.channels.items():
            if key not in self.channels.keys():
                self.channels[key] = value.copy()


    def build(self, context):
        from .asset import normalizePath
        from .geometry import Geometry
        if self.ignore:
            return
        if self.rna is None:
            self.rna = bpy.data.materials.new(self.name)
        scn = self.scene = context.scene
        mat = self.rna
        mat.DazRenderEngine = scn.render.engine
        mat.DazShader = self.shader
        if bpy.app.version < (2,80,0):
            mat.game_settings.alpha_blend = 'CLIP'
        if self.uv_set:
            self.uv_sets[self.uv_set.name] = self.uv_set
        geo = self.geometry
        if geo and isinstance(geo, Geometry):
            for uv,uvset in geo.uv_sets.items():
                if uvset:
                    self.uv_sets[uv] = self.uv_sets[uvset.name] = uvset
        for shell,uvs in self.shells:
            shell.shader = self.shader
        if self.thinGlass:
            mat.DazThinGlass = True


    def postbuild(self, context):
        pass


    def getUvKey(self, key, struct):
        if key in struct.keys():
            return key
        if key[0:7].lower() == "default":
            for key1 in struct.keys():
                if key1[0:7].lower() == "default":
                    print("Alt key: '%s' = '%s'" % (key, key1))
                    return key1
        print("Missing UV for '%s', '%s' not in %s" % (self.name, key, list(struct.keys())))
        return key


    def getUvSet(self, uv):
        key = self.getUvKey(uv, self.uv_sets)
        if key is None:
            return self.uv_set
        elif key not in self.uv_sets.keys():
            uvset = Asset(None)
            uvset.name = key
            self.uv_sets[key] = uvset
        return self.uv_sets[key]


    def fixUdim(self, udim):
        try:
            self.rna.DazUDim = udim
        except ValueError:
            print("UDIM out of range: %d" % udim)
        self.rna.DazVDim = 0
        addUdim(self.rna, udim, 0)


    def fromMaterial(self, mat, ob):
        struct = OrderedDict()
        struct["id"] = mat.name
        self.rna = mat
        return struct


    def getImageFile(self, channel):
        if "image_file" in channel.keys():
            return channel["image_file"]
        elif "literal_image" in channel.keys():
            return channel["literal_image"]
        else:
            return None


    def getGamma(self, channel):
        global theGammas
        url = self.getImageFile(channel)
        gamma = 0
        if url in theGammas.keys():
            gamma = theGammas[url]
        elif "default_image_gamma" in channel.keys():
            gamma = channel["default_image_gamma"]
        return gamma

#-------------------------------------------------------------
#   Get channels
#-------------------------------------------------------------

    def getChannelDiffuse(self):
        return self.getChannel(["diffuse", "Diffuse Color"])

    def getChannelDiffuseStrength(self):
        return self.getChannel(["diffuse_strength", "Diffuse Strength"])

    def getChannelDiffuseRoughness(self):
        return self.getChannel(["Diffuse Roughness"])

    def getChannelSpecularColor(self):
        return self.getTexChannel(["Glossy Color", "specular", "Specular Color"])

    def getChannelSpecularStrength(self):
        return self.getTexChannel(["Glossy Layered Weight", "Glossy Weight", "specular_strength", "Specular Strength"])

    def getChannelGlossyReflectivity(self):
        return self.getChannel(["Glossy Reflectivity"])

    def getChannelGlossyRoughness(self):
        return self.getChannel(["Glossy Roughness"])

    def getChannelGlossySpecular(self):
        return self.getChannel(["Glossy Specular"])

    def getChannelGlossiness(self):
        channel = self.getChannel(["glossiness", "Glossiness"])
        if channel:
            return channel, False
        else:
            return self.getChannel(["Glossy Roughness"]), True

    def getChannelTranslucencyColor(self):
        return self.getChannel(["Translucency Color"])

    def getChannelTranslucencyWeight(self):
        return self.getChannel(["translucency", "Translucency Weight"])

    def getChannelOpacity(self):
        return self.getChannel(["opacity"])

    def getChannelCutoutOpacity(self):
        return self.getChannel(["Cutout Opacity", "transparency"])

    def getChannelAmbientColor(self):
        return self.getChannel(["ambient", "Ambient Color"])

    def getChannelAmbientStrength(self):
        return self.getChannel(["ambient_strength", "Ambient Strength"])

    def getChannelEmissionColor(self):
        return self.getChannel(["emission", "Emission Color"])

    def getChannelReflectionColor(self):
        return self.getChannel(["reflection", "Reflection Color"])

    def getChannelReflectionStrength(self):
        return self.getChannel(["reflection_strength", "Reflection Strength"])

    def getChannelRefractionColor(self):
        return self.getChannel(["refraction", "Refraction Color"])

    def getChannelRefractionStrength(self):
        return self.getChannel(["refraction_strength", "Refraction Weight"])

    def getChannelIOR(self):
        return self.getChannel(["ior", "Refraction Index"])

    def getChannelSSSColor(self):
        return self.getChannel(["Translucency Color", "SSS Color", "Subsurface Color", "SSS Reflectance Tint"])

    def getChannelSSSAmount(self):
        return self.getChannel(["translucency", "Translucency Weight", "SSS Amount", "Subsurface Strength"])

    def getChannelSSSScale(self):
        return self.getChannel(["SSS Scale", "Subsurface Scale"])

    def getChannelSSSRadius(self):
        return self.getChannel(["Scattering Measurement Distance"])

    def getChannelSSSIOR(self):
        return self.getChannel(["Subsurface Refraction"])

    def getChannelTopCoatRoughness(self):
        return self.getChannel(["Top Coat Roughness"])

    def getChannelNormal(self):
        return self.getChannel(["normal", "Normal Map"])

    def getChannelBump(self):
        return self.getChannel(["bump", "Bump Strength"])

    def getChannelBumpMin(self):
        return self.getChannel(["bump_min", "Bump Minimum", "Negative Bump"])

    def getChannelBumpMax(self):
        return self.getChannel(["bump_max", "Bump Maximum", "Positive Bump"])

    def getChannelDisplacement(self):
        return self.getChannel(["displacement", "Displacement Strength"])

    def getChannelDispMin(self):
        return self.getChannel(["displacement_min", "Displacement Minimum", "Minimum Displacement"])

    def getChannelDispMax(self):
        return self.getChannel(["displacement_max", "Displacement Maximum", "Maximum Displacement"])

    def getChannelHorizontalTiles(self):
        return self.getChannel(["u_scale", "Horizontal Tiles"])

    def getChannelHorizontalOffset(self):
        return self.getChannel(["u_offset", "Horizontal Offset"])

    def getChannelVerticalTiles(self):
        return self.getChannel(["v_scale", "Vertical Tiles"])

    def getChannelVerticalOffset(self):
        return self.getChannel(["v_offset", "Vertical Offset"])


    def isActive(self, name):
        cname = "%s Active" % name
        if cname in self.channels.keys():
            channel = self.channels[cname]
            if "current_value" in channel.keys():
                return channel["current_value"]
            elif "value" in channel.keys():
                return channel["value"]
        return True


    def getValue(self, attr, default):
        return self.getChannelValue(self.getChannel(attr), default)


    def getChannel(self, attr):
        if isinstance(attr, str):
            return getattr(self, attr)()
        for key in attr:
            if key in self.channels.keys():
                channel = self.channels[key]
                if ("visible" not in channel.keys() or
                    channel["visible"]):
                    return channel
        return None


    def getTexChannel(self, channels):
        for key in channels:
            channel = self.getChannel([key])
            if channel and self.hasTextures(channel):
                return channel
        return self.getChannel(channels)


    def hasTexChannel(self, channels):
        for key in channels:
            channel = self.getChannel([key])
            if channel and self.hasTextures(channel):
                return True
        return False


    def getChannelValue(self, channel, default, warn=True):
        if channel is None:
            return default
        if (not self.getImageFile(channel) and
            "invalid_without_map" in channel.keys() and
            channel["invalid_without_map"]):
            return default
        for key in ["color", "strength", "current_value", "value"]:
            if key in channel.keys():
                value = channel[key]
                if isVector(default):
                    if isVector(value):
                        return value
                    else:
                        return Vector((value, value, value))
                else:
                    if isVector(value):
                        return (value[0] + value[1] + value[2])/3
                    else:
                        return value
        if warn and theSettings.verbosity > 2:
            print("Did not find value for channel %s" % channel["id"])
            print("Keys: %s" % list(channel.keys()))
        return default


    def getChannelColor(self, channel, default, warn=True):
        color = self.getChannelValue(channel, default, warn)
        if isinstance(color, int) or isinstance(color, float):
            color = (color, color, color)
        return self.srgbToLinear(color)


    def srgbToLinear(self, srgb):
        lin = []
        for s in srgb:
            if s < 0.04045:
                l = s/12.92
            else:
                l = ((s+0.055)/1.055)**2.4
            lin.append(l)
        return Vector(lin)


    def getTextures(self, channel):
        if isinstance(channel, tuple):
            channel = channel[0]
        if channel is None:
            return [],[]
        elif "image" in channel.keys():
            if channel["image"] is None:
                return [],[]
            else:
                maps = self.getAsset(channel["image"]).maps
                if maps is None:
                    maps = []
        elif "image_file" in channel.keys():
            map = Map({}, False)
            map.url = channel["image_file"]
            maps = [map]
        elif "map" in channel.keys():
            maps = Maps(self.fileref)
            maps.parse(channel["map"])
            halt
        elif "literal_image" in channel.keys():
            map = Map(channel, False)
            map.image = channel["literal_image"]
            maps = [map]
        elif "literal_maps" in channel.keys():
            maps = []
            for struct in channel["literal_maps"]["map"]:
                if "mask" in struct.keys():
                    mask = Map(struct["mask"], True)
                    maps.append(mask)
                map = Map(struct, False)
                maps.append(map)
        else:
            return [],[]

        texs = []
        nmaps = []
        for map in maps:
            if map.url:
                tex = map.getTexture()
            elif map.literal_image:
                tex = Texture(map)
                tex.image = map.literal_image
            else:
                tex = None
            if tex:
                texs.append(tex)
                nmaps.append(map)
        return texs,nmaps


    def hasTextures(self, channel):
        return (self.getTextures(channel)[0] != [])


    def hasAnyTexture(self):
        for key in self.channels:
            channel = self.getChannel([key])
            if self.getTextures(channel)[0]:
                return True
        return False


    def dumpChannels(self):
        for key,channel in self.channels.items():
            string = ("%s  %s %s " % (key, channel["value"], channel["current_value"]))
            if "image_file" in channel.keys():
                string += channel["image_file"]
            print(string)


    def sssActive(self):
        if not (self.isActive("Subsurface") and theSettings.useSSS):
            return False
        if self.thinWalled:
            return False
        return True

#-------------------------------------------------------------
#   Textures
#-------------------------------------------------------------

def getRenderMaterial(struct, base):
    from .cycles import CyclesMaterial
    from .internal import InternalMaterial

    if isinstance(base, CyclesMaterial):
        return CyclesMaterial
    elif isinstance(base, InternalMaterial):
        return InternalMaterial

    if theSettings.renderMethod in ['BLENDER_RENDER', 'BLENDER_GAME']:
        return InternalMaterial
    else:
        return CyclesMaterial

#-------------------------------------------------------------
#   Textures
#-------------------------------------------------------------

class Map:
    def __init__(self, map, ismask):
        self.url = None
        self.label = None
        self.operation = "alpha_blend"
        self.color = (1,1,1)
        self.ismask = ismask
        self.image = None
        self.size = None
        for key,default in [
            ("url", None),
            ("color", BLACK),
            ("label", None),
            ("operation", "alpha_blend"),
            ("literal_image", None),
            ("invert", False),
            ("transparency", 1),
            ("rotation", 0),
            ("xmirror", False),
            ("ymirror", False),
            ("xscale", 1),
            ("yscale", 1),
            ("xoffset", 0),
            ("yoffset", 0)]:
            if key in map.keys():
                setattr(self, key, map[key])
            else:
                setattr(self, key, default)


    def __repr__(self):
        return ("<Map %s %s %s (%s %s)>" % (self.image, self.ismask, self.size, self.xoffset, self.yoffset))


    def getTexture(self):
        global theTextures
        if self.url in theTextures.keys():
            return theTextures[self.url]
        else:
            tex = Texture(self)
        if self.url:
            theTextures[self.url] = tex
        return tex


    def build(self):
        global theImages
        if self.image:
            return self.image
        elif self.url:
            if self.url in theImages.keys():
                self.image = theImages[self.url]
            else:
                self.image = loadImage(self.url)
            return self.image
        else:
            return self


def loadImage(url):
    from .asset import getDazPath
    global theImages
    filepath = getDazPath(url)
    if filepath is None:
        img = None
        if theSettings.verbosity > 2:
            print('Image not found:  \n"%s"' % filepath)
    else:
        img = bpy.data.images.load(filepath)
        img.name = os.path.splitext(os.path.basename(filepath))[0]
        theImages[url] = img
    return img


class Images(Asset):
    def __init__(self, fileref):
        Asset.__init__(self, fileref)
        self.maps = []


    def __repr__(self):
        return ("<Images %s r: %s>" % (self.id, self.maps))


    def parse(self, struct):
        Asset.parse(self, struct)
        mapSize = None
        for key in struct.keys():
            if key == "map":
                for mstruct in struct["map"]:
                    if "mask" in mstruct.keys():
                        self.maps.append(Map(mstruct["mask"], True))
                    self.maps.append(Map(mstruct, False))
            elif key == "map_size":
                mapSize = struct[key]
        if mapSize is not None:
            for map in self.maps:
                map.size = mapSize
        self.parseGamma(struct)


    def update(self, struct):
        self.parseGamma(struct)


    def parseGamma(self, struct):
        global theGammas
        if "map_gamma" in struct.keys():
            gamma = struct["map_gamma"]
            for map in self.maps:
                theGammas[map.url] = gamma


    def build(self):
        images = []
        for map in self.maps:
            img = map.build()
            images.append(img)
        return images


def setImageColorSpace(img, colorspace):
    try:
        img.colorspace_settings.name = colorspace
        return
    except TypeError:
        pass
    alternatives = {
        "sRGB" : ["sRGB OETF"],
        "Non-Color" : ["Non-Colour Data"],
    }
    for alt in alternatives[colorspace]:
        try:
            img.colorspace_settings.name = alt
            return
        except TypeError:
            pass


class Texture:

    def __init__(self, map):
        self.rna = None
        self.map = map
        self.built = {"COLOR":False, "NONE":False}
        self.images = {"COLOR":None, "NONE":None}

    def __repr__(self):
        return ("<Texture %s %s %s>" % (self.map.url, self.map.image, self.image))


    def buildInternal(self):
        global theTextures
        if self.built["COLOR"]:
            return self

        if self.map.url:
            key = self.map.url
        elif self.map.image:
            key = self.map.image.name
        else:
            key = None

        if key is not None:
            img = self.images["COLOR"] = self.map.build()
            if img:
                tex = self.rna = bpy.data.textures.new(img.name, 'IMAGE')
                tex.image = img
            else:
                tex = None
            theTextures[key] = self
        else:
            tex = self.rna = bpy.data.textures.new(self.map.label, 'BLEND')
            tex.use_color_ramp = True
            r,g,b = self.map.color
            for elt in tex.color_ramp.elements:
                elt.color = (r,g,b,1)
        self.built["COLOR"] = True
        return self


    def buildCycles(self, colorSpace):
        if self.built[colorSpace]:
            return self.images[colorSpace]
        elif colorSpace == "COLOR" and self.images["NONE"]:
            img = self.images["NONE"].copy()
        elif colorSpace == "NONE" and self.images["COLOR"]:
            img = self.images["COLOR"].copy()            
        elif self.map.url:
            img = self.map.build()
        elif self.map.image:
            img = self.map.image
        else:
            img = None
        if hasattr(img, "colorspace_settings"):
            if colorSpace == "COLOR":
                img.colorspace_settings.name = "sRGB"
            elif colorSpace == "NONE":
                img.colorspace_settings.name = "Non-Color"
            else:
                img.colorspace_settings.name = colorSpace
        if img:
            self.images[colorSpace] = img             
        self.built[colorSpace] = True
        return img


    def hasMapping(self, map):
        if map:
            return (map.size is not None)
        else:
            return (self.map and self.map.size is not None)


    def getMapping(self, mat, map):
        # mapping scale x = texture width / lie document size x * (lie x scale / 100)
        # mapping scale y = texture height / lie document size y * (lie y scale / 100)
        # mapping location x = udim place + lie x position * (lie y scale / 100) / lie document size x
        # mapping location y = (lie document size y - texture height * (lie y scale / 100) - lie y position) / lie document size y

        if self.images["COLOR"]:
            img = self.images["COLOR"]
        elif self.images["NONE"]:
            img = self.images["NONE"]
        else:
            raise RuntimeError("BUG: getMapping finds no image")

        tx,ty = img.size
        mx,my = map.size
        kx,ky = tx/mx,ty/my
        ox,oy = map.xoffset/mx, map.yoffset/my
        rz = map.rotation

        ox += mat.getChannelValue(mat.getChannelHorizontalOffset(), 0)
        oy += mat.getChannelValue(mat.getChannelVerticalOffset(), 0)
        kx *= mat.getChannelValue(mat.getChannelHorizontalTiles(), 1)
        ky *= mat.getChannelValue(mat.getChannelVerticalTiles(), 1)

        sx = map.xscale*kx
        sy = map.yscale*ky

        if rz == 0:
            dx = ox
            dy = 1 - sy - oy
            if map.xmirror:
                dx = sx + ox
                sx = -sx
            if map.ymirror:
                dy = 1 - oy
                sy = -sy
        elif rz == 90:
            dx = ox
            dy = 1 - oy
            if map.xmirror:
                dy = 1 - sy - oy
                sy = -sy
            if map.ymirror:
                dx = sx + ox
                sx = -sx
            tmp = sx
            sx = sy
            sy = tmp
            rz = 270*D
        elif rz == 180:
            dx = sx + ox
            dy = 1 - oy
            if map.xmirror:
                dx = ox
                sx = -sx
            if map.ymirror:
                dy = 1 - sy - oy
                sy = -sy
            rz = 180*D
        elif rz == 270:
            dx = sx + ox
            dy = 1 - sy - oy
            if map.xmirror:
                dy = 1 - oy
                sy = -sy
            if map.ymirror:
                dx = ox
                sx = -sx
            tmp = sx
            sx = sy
            sy = tmp
            rz = 90*D

        return (dx,dy,sx,sy,rz)


def addUdim(mat, udim, vdim):
    if mat.node_tree:
        addUdimTree(mat.node_tree, udim, vdim)
    else:
        for mtex in mat.texture_slots:
            if mtex and mtex.texture and mtex.texture.extension == 'CLIP':
                mtex.offset[0] += udim
                mtex.offset[1] += vdim


def addUdimTree(tree, udim, vdim):
    for node in tree.nodes:
        if node.type == 'MAPPING':
            if hasattr(node, "translation"):
                slot = node.translation
            else:
                slot = node.inputs["Location"].default_value
            slot[0] += udim
            slot[1] += vdim
        elif node.type == 'GROUP':
            addUdimTree(node.node_tree, udim, vdim)

#-------------------------------------------------------------z
#
#-------------------------------------------------------------

def clearMaterials():
    global theImages, theTextures, theGammas
    theImages = {}
    theTextures = {}
    theGammas = {}


clearMaterials()


def isWhite(color):
    return (tuple(color[0:3]) == (1.0,1.0,1.0))


def isBlack(color):
    return (tuple(color[0:3]) == (0.0,0.0,0.0))

#-------------------------------------------------------------
#   Save local textures
#-------------------------------------------------------------

def saveLocalTextureCopies(context):
    from shutil import copyfile
    if not bpy.data.filepath:
        raise DazError("Save the blend file first")
    texpath = os.path.join(os.path.dirname(bpy.data.filepath), "textures")
    print("Save textures to '%s'" % texpath)
    if not os.path.exists(texpath):
        os.makedirs(texpath)

    images = []
    for ob in getSceneObjects(context):
        if ob.type == 'MESH':
            for mat in ob.data.materials:
                if mat and mat.use_nodes:
                    saveNodesInTree(mat.node_tree, images)
                elif mat:
                    for mtex in mat.texture_slots:
                        if mtex:
                            tex = mtex.texture
                            if hasattr(tex, "image") and tex.image:
                                images.append(tex.image)


    for img in images:
        src = bpy.path.abspath(img.filepath)
        src = bpy.path.reduce_dirs([src])[0]
        trg = os.path.join(texpath, bpy.path.basename(src))
        if src != trg and not os.path.exists(trg):
            print("Copy %s\n => %s" % (src, trg))
            copyfile(src, trg)
        img.filepath = bpy.path.relpath(trg)


def saveNodesInTree(tree, images):                    
    for node in tree.nodes.values():
        if node.type == 'TEX_IMAGE':
            images.append(node.image)
        elif node.type == 'GROUP':
            saveNodesInTree(node.node_tree, images)


class DAZ_OT_SaveLocalTextures(bpy.types.Operator):
    bl_idname = "daz.save_local_textures"
    bl_label = "Save Local Textures"
    bl_description = "Copy textures to the textures subfolder in the blend file's directory"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return context.object

    def execute(self, context):
        try:
            saveLocalTextureCopies(context)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}

#-------------------------------------------------------------
#   Merge identical materials
#-------------------------------------------------------------

def mergeMaterials(ob):
    if ob.type != 'MESH':
        return

    matlist = []
    assoc = {}
    reindex = {}
    m = 0
    reduced = False
    for n,mat1 in enumerate(ob.data.materials):
        unique = True
        for mat2 in matlist:
            if areSameMaterial(mat1, mat2):
                reindex[n] = assoc[mat2.name]
                unique = False
                reduced = True
                break
        if unique:
            matlist.append(mat1)
            reindex[n] = assoc[mat1.name] = m
            m += 1
    if reduced:
        for f in ob.data.polygons:
            f.material_index = reindex[f.material_index]
        for n,mat in enumerate(matlist):
            ob.data.materials[n] = mat
        for n in range(len(matlist), len(ob.data.materials)):
            ob.data.materials.pop()


def areSameMaterial(mat1, mat2):
    deadMatProps = [
        "texture_slots", "node_tree",
        "name", "name_full", "active_texture",
    ]
    matProps = getRelevantProps(mat1, deadMatProps)
    if not haveSameAttrs(mat1, mat2, matProps):
        return False
    if mat1.use_nodes and mat2.use_nodes:
        if areSameCycles(mat1.node_tree, mat2.node_tree):
            print(mat1.name, "=", mat2.name)
            return True
    elif mat1.use_nodes or mat2.use_nodes:
        return False
    elif areSameInternal(mat1.texture_slots, mat2.texture_slots):
        print(mat1.name, "=", mat2.name)
        return True
    else:
        return False


def getRelevantProps(rna, deadProps):
    props = []
    for prop in dir(rna):
        if (prop[0] != "_" and
            prop not in deadProps):
            props.append(prop)
    return props


def haveSameAttrs(rna1, rna2, props):
    for prop in props:
        attr1 = attr2 = None
        if hasattr(rna1, prop) and hasattr(rna2, prop):
            attr1 = getattr(rna1, prop)
            attr2 = getattr(rna2, prop)
            if not checkEqual(attr1, attr2):
                return False
        elif hasattr(rna1, prop) or hasattr(rna2, prop):
            return False
    return True


def checkEqual(attr1, attr2):
    if (isinstance(attr1, int) or
        isinstance(attr1, float) or
        isinstance(attr1, str)):
        return (attr1 == attr2)
    if isinstance(attr1, bpy.types.Image):
        return (isinstance(attr2, bpy.types.Image) and (attr1.name == attr2.name))
    if (isinstance(attr1, set) and isinstance(attr2, set)):
        return True
    if hasattr(attr1, "__len__") and hasattr(attr2, "__len__"):
        if (len(attr1) != len(attr2)):
            return False
        for n in range(len(attr1)):
            if not checkEqual(attr1[n], attr2[n]):
                return False
    return True


def areSameCycles(tree1, tree2):
    if not haveSameKeys(tree1.nodes, tree2.nodes):
        return False
    if not haveSameKeys(tree1.links, tree2.links):
        return False
    for key,node1 in tree1.nodes.items():
        node2 = tree2.nodes[key]
        if not areSameNode(node1, node2):
            return False
    for link1 in tree1.links:
        hit = False
        for link2 in tree2.links:
            if areSameLink(link1, link2):
                hit = True
                break
        if not hit:
            return False
    for link2 in tree2.links:
        hit = False
        for link1 in tree1.links:
            if areSameLink(link1, link2):
                hit = True
                break
        if not hit:
            return False
    return True


def areSameNode(node1, node2):
    if not haveSameKeys(node1, node2):
        return False
    deadNodeProps = ["dimensions", "location"]
    nodeProps = getRelevantProps(node1, deadNodeProps)
    if not haveSameAttrs(node1, node2, nodeProps):
        return False
    if not haveSameInputs(node1, node2):
        return False
    return True


def areSameLink(link1, link2):
    return (
        (link1.from_node.name == link2.from_node.name) and
        (link1.to_node.name == link2.to_node.name) and
        (link1.from_socket.name == link2.from_socket.name) and
        (link1.to_socket.name == link2.to_socket.name)
    )


def haveSameInputs(nodes1, nodes2):
    if len(nodes1.inputs) != len(nodes2.inputs):
        return False
    for n,socket1 in enumerate(nodes1.inputs):
        socket2 = nodes2.inputs[n]
        if hasattr(socket1, "default_value"):
            if not hasattr(socket2, "default_value"):
                return False
            val1 = socket1.default_value
            val2 = socket2.default_value
            if (hasattr(val1, "__len__") and
                hasattr(val2, "__len__")):
                for m in range(len(val1)):
                    if val1[m] != val2[m]:
                        return False
            elif val1 != val2:
                return False
        elif hasattr(socket2, "default_value"):
            return False
    return True


def haveSameKeys(struct1, struct2):
    for key in struct1.keys():
        if key not in struct2.keys():
            return False
    return True


def areSameInternal(mtexs1, mtexs2):
    if len(mtexs1) != len(mtexs2):
        return False
    if len(mtexs1) == 0:
        return True

    deadMtexProps = [
        "name", "output_node",
    ]
    mtexProps = getRelevantProps(mtexs1[0], deadMtexProps)

    for n,mtex1 in enumerate(mtexs1):
        mtex2 = mtexs2[n]
        if mtex1 is None and mtex2 is None:
            continue
        if mtex1 is None or mtex2 is None:
            return False
        if not haveSameAttrs(mtex1, mtex2, mtexProps):
            return False
        if hasattr(mtex1.texture, "image"):
            img1 = mtex1.texture.image
        else:
            img1 = None
        if hasattr(mtex2.texture, "image"):
            img2 = mtex2.texture.image
        else:
            img2 = None
        if img1 is None and img2 is None:
            continue
        if img1 is None or img2 is None:
            return False
        if img1.filepath != img2.filepath:
            return False

    return True


class DAZ_OT_MergeMaterials(bpy.types.Operator):
    bl_idname = "daz.merge_materials"
    bl_label = "Merge Materials"
    bl_description = "Merge identical materials"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

    def execute(self, context):
        try:
            for ob in getSceneObjects(context):
                if getSelected(ob):
                    mergeMaterials(ob)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}

# ---------------------------------------------------------------------
#   Tweak bump strength and height
#
#   (node type, socket, BI use, BI factor, isColor)
# ---------------------------------------------------------------------

TweakableChannels = OrderedDict([
    ("Bump Strength", ("BUMP", "Strength", "use_map_normal", "normal_factor", 1)),
    ("Bump Distance", ("BUMP", "Distance", None, None, 1)),
    ("Normal Strength", ("NORMAL_MAP", "Strength", "use_map_normal", "normal_factor", 1)),

    ("Diffuse Color", ("BSDF_DIFFUSE", "Color", None, None, 4)),
    ("Diffuse Roughness", ("BSDF_DIFFUSE", "Roughness", None, None, 1)),

    ("Glossy Color", ("BSDF_GLOSSY", "Color", None, None, 4)),
    ("Glossy Roughness", ("BSDF_GLOSSY", "Roughness", None, None, 1)),

    ("Translucency Color", ("BSDF_TRANSLUCENT", "Color", "use_map_translucency", "translucency_factor", 4)),

    ("Subsurface Color", ("SUBSURFACE_SCATTERING", "Color", None, None, 4)),
    ("Subsurface Scale", ("SUBSURFACE_SCATTERING", "Scale", None, None, 1)),
    ("Subsurface Radius", ("SUBSURFACE_SCATTERING", "Radius", None, None, 3)),

    ("Principled Base Color", ("BSDF_PRINCIPLED", "Base Color", None, None, 4)),
    ("Principled Metallic", ("BSDF_PRINCIPLED", "Metallic", None, None, 1)),
    ("Principled Specular", ("BSDF_PRINCIPLED", "Specular", None, None, 1)),
    ("Principled Subsurface", ("BSDF_PRINCIPLED", "Subsurface", None, None, 1)),
    ("Principled Subsurface Color", ("BSDF_PRINCIPLED", "Subsurface Color", None, None, 4)),
    ("Principled Subsurface Radius", ("BSDF_PRINCIPLED", "Subsurface Radius", None, None, 3)),
    ("Principled Roughness", ("BSDF_PRINCIPLED", "Roughness", None, None, 1)),
    ("Principled Clearcoat", ("BSDF_PRINCIPLED", "Clearcoat", None, None, 1)),
    ("Principled Clearcoat Roughness", ("BSDF_PRINCIPLED", "Clearcoat Roughness", None, None, 1)),
])

def printItem(string, item):
    print(string, "<Factor %s %.4f (%.4f %.4f %.4f %.4f) %s>" % (item.key, item.value, item.color[0], item.color[1], item.color[2], item.color[3], item.new))


def isRefractive(mat):
    if mat.use_nodes:
        for node in mat.node_tree.nodes.values():
            if node.type in ["BSDF_TRANSPARENT", "BSDF_REFRACTION"]:
                return True
            elif node.type == "BSDF_PRINCIPLED":
                if (inputDiffers(node, "Alpha", 1) or
                    inputDiffers(node, "Transmission", 0)):
                    return True
        return False
                
                
def inputDiffers(node, slot, value):
    if slot in node.inputs.keys():
        if node.inputs[slot].default_value != value:
            return True
    return False                


class ChannelChanger:
    def getNewChannelFactor(self, ob, key):
        for item in ob.DazChannelFactors:
            if item.key == key:
                return item
        item = ob.DazChannelFactors.add()
        item.key = key
        item.new = True
        return item
   
   
    def setChannel(self, ob, key, item, scn):
        from .guess import getSkinMaterial
        nodetype, slot, useAttr, factorAttr, ncomps = TweakableChannels[key]
        tweaktype = scn.DazTweakMaterials
        for mat in ob.data.materials:            
            if mat and mat.use_nodes:

                if isRefractive(mat) and tweaktype not in ["Refractive", "All"]:
                    continue
                mattype, = getSkinMaterial(mat)
                if tweaktype == "Skin":
                    if mattype != "Skin":
                        continue
                elif tweaktype == "Skin-Lips-Nails":
                    if mattype not in ["Skin", "Red"]:
                        continue
                
                for node in mat.node_tree.nodes.values():
                    if node.type == nodetype:
                        socket = node.inputs[slot]
                        self.setOriginal(socket, ncomps, item)
                        self.setSocket(socket, ncomps, item, scn)
                        fromnode = None
                        for link in mat.node_tree.links.values():
                            if link.to_node == node and link.to_socket == socket:
                                fromnode = link.from_node
                                fromsocket = link.from_socket
                                break
                        if fromnode:
                            if fromnode.type == "MIX_RGB":
                                self.setSocket(fromnode.inputs[1], ncomps, item, scn)
                            elif fromnode.type == "MATH" and fromnode.operation == 'MULTIPLY':
                                self.setSocket(fromnode.inputs[0], 1, item, scn)
                            elif fromnode.type == "TEX_IMAGE":
                                mix = self.addMixRGB(scn.DazColorFactor, fromsocket, socket, mat.node_tree)
            elif mat and useAttr:
                for mtex in mat.texture_slots:
                    if mtex and getattr(mtex, useAttr):
                        value = getattr(mtex, factorAttr)
                        setattr(mtex, factorAttr, DazFactor*value)
    
    
    def addMixRGB(self, color, fromsocket, tosocket, tree):
        mix = tree.nodes.new(type = "ShaderNodeMixRGB")
        mix.blend_type = 'MULTIPLY'
        mix.inputs[0].default_value = 1.0
        mix.inputs[1].default_value = color
        tree.links.new(fromsocket, mix.inputs[2])
        tree.links.new(mix.outputs[0], tosocket)
        return mix
           
            
    def setOriginal(self, socket, ncomps, item):
        if item.new:
            x = socket.default_value
            if ncomps == 1:
                item.value = x
                item.color = (x,x,x,1)
            else:
                item.value = x[0]
                for n in range(ncomps):
                    item.color[n] = x[n]
            item.new = False
            

    def setSocket(self, socket, ncomps, item, scn):
        fac = scn.DazFactor
        if self.reset:
            if ncomps == 1:
                socket.default_value = item.value
            else:
                for n in range(ncomps):
                    socket.default_value[n] = item.color[n]        
        elif scn.DazAbsoluteTweak:
            if ncomps == 1:
                socket.default_value = fac
            elif ncomps == 3:
                socket.default_value = (fac,fac,fac)
            else:
                for n in range(ncomps):
                    socket.default_value[n] = scn.DazColorFactor[n]
        else:
            if ncomps == 1:
                socket.default_value *= fac
            elif ncomps == 3:
                for n in range(ncomps):
                    socket.default_value[n] *= fac
            else:
                for n in range(ncomps):
                    socket.default_value[n] *= scn.DazColorFactor[n]
         
    
class DAZ_OT_ChangeChannel(bpy.types.Operator, ChannelChanger, SlotString, UseInternalBool):
    bl_idname = "daz.change_channel"
    bl_label = "Change Channel"
    bl_description = "Multiply active channel of all selected meshes"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

    def execute(self, context):
        try:
            scn = context.scene
            self.reset = False
            for ob in getSceneObjects(context):
                if getSelected(ob) and ob.type == 'MESH':
                    key = scn.DazTweakableChannel
                    item = self.getNewChannelFactor(ob, key)
                    self.setChannel(ob, key, item, scn)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}


class DAZ_OT_ResetMaterial(bpy.types.Operator, ChannelChanger):
    bl_idname = "daz.reset_material"
    bl_label = "Reset Material"
    bl_description = "Reset material to original"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

    def execute(self, context):
        try:
            scn = context.scene
            self.reset = True
            for ob in getSceneObjects(context):
                if getSelected(ob) and ob.type == 'MESH':
                    for item in ob.DazChannelFactors:
                        nodetype, slot, useAttr, factorAttr, ncomps = TweakableChannels[item.key]
                        self.setChannel(ob, item.key, item, scn)
                        item.new = True
        except DazError:
            handleDazError(context)
        return{'FINISHED'}

# ---------------------------------------------------------------------
#   Toggle SSS and displacement for BI
# ---------------------------------------------------------------------

class DAZ_OT_ToggleSSS(bpy.types.Operator):
    bl_idname = "daz.toggle_sss"
    bl_label = "Toggle SSS"
    bl_description = "Toggle subsurface scattering on/off for selected meshes"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

    def execute(self, context):
        value = 0 if context.object.DazUseSSS else 1
        for ob in getSceneObjects(context):
            if getSelected(ob) and ob.type == 'MESH':
                for mat in ob.data.materials:
                    if mat.DazUseSSS:
                        if mat.node_tree:
                            for link in mat.node_tree.links:
                                if link.from_node.type == 'SUBSURFACE_SCATTERING':
                                    mix = link.to_node
                                    if mix.type == 'MIX_SHADER':
                                        mix.inputs[0].default_value = 0.5*value
                        else:
                            mat.subsurface_scattering.use = value
                ob.DazUseSSS = value
        return{'FINISHED'}


class DAZ_OT_ToggleDisplacement(bpy.types.Operator):
    bl_idname = "daz.toggle_displacement"
    bl_label = "Toggle Displacement"
    bl_description = "Toggle displacement on/off for selected meshes"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

    def execute(self, context):
        value = False if context.object.DazUseDisplacement else True
        for ob in getSceneObjects(context):
            if getSelected(ob) and ob.type == 'MESH':
                for mat in ob.data.materials:
                    if mat.node_tree:
                        pass
                    else:
                        for n,mtex in enumerate(mat.texture_slots):
                            if mtex and mtex.use_map_displacement:
                                mat.use_textures[n] = value
                ob.DazUseDisplacement = value
        return{'FINISHED'}

# ---------------------------------------------------------------------
#   Share materials
# ---------------------------------------------------------------------

class DAZ_OT_ShareMaterials(bpy.types.Operator):
    bl_idname = "daz.share_materials"
    bl_label = "Share Materials"
    bl_description = "Share material of all selected meshes to active material"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

    def execute(self, context):
        try:
            ob = context.object
            mat = ob.data.materials[ob.active_material_index]
            for ob in getSceneObjects(context):
                if getSelected(ob) and ob.type == 'MESH':
                    ob.data.materials.clear()
                    ob.data.materials.append(mat)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}

# ---------------------------------------------------------------------
#   Share materials
# ---------------------------------------------------------------------

class DAZ_OT_LoadMaterial(bpy.types.Operator, DazImageFile, MultiFile):
    bl_idname = "daz.load_materials"
    bl_label = "Load Material(s)"
    bl_description = "Load materials to active mesh"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

    def execute(self, context):
        try:
            self.loadMaterials(context)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}


    def invoke(self, context, event):
        from .fileutils import getFolder
        folder = getFolder(context.object, context.scene, ["Materials/"])
        if folder is not None:
            self.properties.filepath = folder
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


    def loadMaterials(self, context):
        from .fileutils import getMultiFiles
        from .globvars import theDazExtensions
        from .readfile import readDufFile
        from .files import parseAssetFile

        ob = context.object
        scn = context.scene
        theSettings.forMaterial(ob, scn)
        paths = getMultiFiles(self, theDazExtensions)
        for path in paths:
            struct = readDufFile(path)
            fasset = parseAssetFile(struct)
            if fasset is None or len(fasset.materials) == 0:
                raise DazError ("Not a material asset:\n  '%s'" % path)
            print(fasset)
            for masset in fasset.materials:
                print("  ", masset)
                masset.build(context)
                print(" B", masset)
                updateScene(context)
                masset.postbuild(context)

        ob.data.materials.clear()
        print("Loaded")

# ---------------------------------------------------------------------
#   Resize textures
# ---------------------------------------------------------------------

class ChangeResolution:
    def __init__(self):
        self.filenames = []
        self.images = {}


    def getFileNames(self, paths):
        for path in paths:
            fname = bpy.path.basename(self.getBasePath(path))
            self.filenames.append(fname)


    def replaceTextures(self, context):
        for ob in getSceneObjects(context):
            if ob.type == 'MESH' and getSelected(ob):
                for mat in ob.data.materials:
                    if mat.node_tree:
                        self.resizeTree(mat.node_tree)
                    else:
                        for mtex in mat.texture_slots:
                            if mtex and mtex.texture.type == 'IMAGE':
                                mtex.texture.image = self.replaceImage(mtex.texture.image)


    def resizeTree(self, tree):
        for node in tree.nodes.values():
            if node.type == 'TEX_IMAGE':
                newimg = self.replaceImage(node.image)
                node.image = newimg
            elif node.type == 'GROUP':
                self.resizeTree(node.node_tree)


    def getBasePath(self, path):
        fname,ext = os.path.splitext(path)
        if fname[-5:] == "-res0":
            return fname[:-5] + ext        
        elif fname[-5:-1] == "-res" and fname[-1].isdigit():
            return fname[:-5] + ext
        else:
            return path


    def replaceImage(self, img):
        if img is None:
            return None
        path = self.getBasePath(img.filepath)
        filename = bpy.path.basename(path)
        if filename not in self.filenames:
            return img

        if self.overwrite:
            if img.filepath in self.images.keys():
                return self.images[img.filepath][1]
            try:
                print("Reload", img.filepath)
                img.reload()
                newimg = img
            except RuntimeError:
                newimg = None
            if newimg:
                self.images[img.filepath] = (img, newimg)
                return newimg
            else:
                print("Cannot reload '%s'" % img.filepath)
                return img

        newname,newpath = self.getNewPath(path)
        if newpath == img.filepath:
            return img
        elif newpath in self.images.keys():
            return self.images[newpath][1]
        elif newname in bpy.data.images.keys():
            return bpy.data.images[newname]
        elif newpath in bpy.data.images.keys():
            return bpy.data.images[newpath]
        else:
            try:
                print("Replace '%s'\n   with '%s'" % (img.filepath, newpath))
                newimg = bpy.data.images.load(newpath)
            except RuntimeError:
                newimg = None
        if newimg:
            self.images[newpath] = (img, newimg)
            return newimg
        else:
            print('"%s" does not exist' % newpath)
            return img


    def getNewPath(self, path):        
        base,ext = os.path.splitext(path)
        if self.steps == 0:
            newbase = base
        else:
            newbase = ("%s-res%d" % (base, self.steps))
        newname = bpy.path.basename(newbase)
        newpath = newbase + ext
        return newname, newpath


class DAZ_OT_ChangeResolution(bpy.types.Operator, ResizeOptions, ChangeResolution):
    bl_idname = "daz.change_resolution"
    bl_label = "Change Resolution"
    bl_description = (
        "Change all textures of selected meshes with resized versions.\n" +
        "The resized textures must already exist.")
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

    def draw(self, context):
        self.layout.prop(self, "steps")

    def execute(self, context):
        try:
            self.changeResolution(context)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.invoke_props_dialog(self)
        return {'RUNNING_MODAL'}


    def changeResolution(self, context):
        self.overwrite = False
        self.getAllTextures(context)
        self.getFileNames(self.paths.keys())
        self.replaceTextures(context)                
    

    def getAllTextures(self, context):
        self.paths = {}
        for ob in getSceneObjects(context):
            if ob.type == 'MESH' and getSelected(ob):
                for mat in ob.data.materials:
                    if mat.node_tree:
                        self.getTreeTextures(mat.node_tree)
                    else:
                        for mtex in mat.texture_slots:
                            if mtex and mtex.texture.type == 'IMAGE':
                                self.paths[mtex.texture.image.filepath] = True
        return self.paths.keys()


    def getTreeTextures(self, tree):
        for node in tree.nodes.values():
            if node.type == 'TEX_IMAGE':
                self.paths[node.image.filepath] = True
            elif node.type == 'GROUP':
                self.resizeTree(node.node_tree)


class DAZ_OT_ResizeTextures(bpy.types.Operator, ImageFile, MultiFile, ResizeOptions, ChangeResolution):
    bl_idname = "daz.resize_textures"
    bl_label = "Resize Textures"
    bl_description = (
        "Replace all textures of selected meshes with resized versions.\n" +
        "Python and OpenCV must be installed on your system.")
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return (context.object and context.object.type == 'MESH')

    def execute(self, context):
        try:
            self.resizeTextures(context)
        except DazError:
            handleDazError(context)
        return{'FINISHED'}

    def invoke(self, context, event):
        texpath = os.path.join(os.path.dirname(bpy.data.filepath), "textures/")
        self.properties.filepath = texpath
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def resizeTextures(self, context):
        from .fileutils import getMultiFiles
        from .globvars import theImageExtensions
        paths = getMultiFiles(self, theImageExtensions)
        self.getFileNames(paths)
        
        program = os.path.join(os.path.dirname(__file__), "standalone/resize.py")
        if self.overwrite:
            overwrite = "-o"
        else:
            overwrite = ""
        for path in paths:                    
            _,newpath = self.getNewPath(self.getBasePath(path))
            if not os.path.exists(newpath):
                cmd = ('python "%s" "%s" %d %s' % (program, path, self.steps, overwrite))
                os.system(cmd)
            else:
                print("Skip", os.path.basename(newpath))
        
        self.replaceTextures(context)                

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    DazChannelFactor,
    DAZ_OT_SaveLocalTextures,
    DAZ_OT_MergeMaterials,
    DAZ_OT_ChangeChannel,
    DAZ_OT_ResetMaterial,
    DAZ_OT_ToggleSSS,
    DAZ_OT_ToggleDisplacement,
    DAZ_OT_ShareMaterials,
    DAZ_OT_LoadMaterial,
    DAZ_OT_ChangeResolution,
    DAZ_OT_ResizeTextures,
]

def initialize():
    for cls in classes:
        bpy.utils.register_class(cls)
        
    bpy.types.Scene.DazNewColor = FloatVectorProperty(
        name = "New Color",
        subtype = "COLOR",
        size = 4,
        min = 0.0,
        max = 1.0,
        default = (0.1, 0.1, 0.5, 1)
    )

    bpy.types.Scene.DazColorFactor = FloatVectorProperty(
        name = "Color Factor/Value",
        subtype = "COLOR",
        size = 4,
        min = 0,
        default = (1, 1, 1, 1)
    )        

    bpy.types.Scene.DazTweakableChannel = EnumProperty(
        items = [(key,key,key) for key in TweakableChannels.keys()],
        name = "Active Channel",
        description = "Active channel to be tweaked",
        default = "Bump Strength")

    bpy.types.Scene.DazFactor = FloatProperty(
        name = "Factor/Value",
        description = "Set/Multiply active channel with this factor",
        min = 0,
        default = 1.0)

    bpy.types.Scene.DazAbsoluteTweak = BoolProperty(
        name = "Absolute Values",
        description = "Tweak channels with absolute values",
        default = False)

    bpy.types.Scene.DazTweakMaterials = EnumProperty(
        items = [("Skin", "Skin", "Skin"),
                 ("Skin-Lips-Nails", "Skin-Lips-Nails", "Skin-Lips-Nails"),
                 ("Opaque", "Opaque", "Opaque"),
                 ("Refractive", "Refractive", "Refractive"),
                 ("All", "All", "All")],
        name = "Material Type",
        description = "Type of materials to tweak",
        default = "Skin")

    bpy.types.Object.DazChannelFactors = CollectionProperty(type = DazChannelFactor)
    bpy.types.Object.DazChannelValues = CollectionProperty(type = DazChannelFactor)
    

def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
