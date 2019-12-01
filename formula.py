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
import math
from mathutils import *
from .error import DazError, raiseOrReportError
from .asset import *
from .utils import *
from .settings import theSettings

#-------------------------------------------------------------
#   Formula
#-------------------------------------------------------------

class Formula:

    def __init__(self):
        self.formulas = []
        self.built = False


    def parse(self, struct):
        if (theSettings.useFormulas and
            "formulas" in struct.keys()):
            self.formulas = struct["formulas"]


    def prebuild(self, context, inst):
        from .modifier import Morph
        from .node import Node
        for formula in self.formulas:
            ref,key,value = self.computeFormula(formula)
            if ref is None:
                continue
            asset = self.getAsset(ref)
            if asset is None:
                continue
            if key == "value" and isinstance(asset, Morph):
                asset.build(context, inst, value)
            elif isinstance(asset, Node):
                inst = asset.getInstance(self.caller, ref, False)
                if inst:
                    inst.addToOffset(self.name, key, value)


    def build(self, context, inst):
        from .morphing import addToCategories
        from .driver import setFloatProp, setBoolProp
        rig = inst.rna
        if rig.pose is None:
            return
        errors = {}
        props = buildPropFormula(self, scn, rig, "Imported", "", errors)
        addToCategories(rig, props, "Imported")
        for prop in props:
            setFloatProp(rig, prop, self.value)
            setBoolProp(rig, "DzA"+prop, True)


    def postbuild(self, context, inst):
        from .modifier import Morph
        from .node import Node
        if not theSettings.useMorph:
            return
        for formula in self.formulas:
            ref,key,value = self.computeFormula(formula)
            if ref is None:
                continue
            asset = self.getAsset(ref)
            if isinstance(asset, Morph):
                pass
            elif isinstance(asset, Node):
                inst = asset.getInstance(self.caller, ref, False)
                if inst:
                    inst.formulate(key, value)


    def computeFormula(self, formula):
        if len(formula["operations"]) != 3:
            return None,None,0
        stack = []
        for struct in formula["operations"]:
            op = struct["op"]
            if op == "push":
                if "url" in struct.keys():
                    ref,key = getRefKey(struct["url"])
                    if ref is None or key != "value":
                        return None,None,0
                    asset = self.getAsset(ref)
                    if not hasattr(asset, "value"):
                        return None,None,0
                    stack.append(asset.value)
                elif "val" in struct.keys():
                    data = struct["val"]
                    stack.append(data)
                else:
                    raiseOrReportError("Cannot push %s" % struct.keys(), 0, 4)
            elif op == "mult":
                x = stack[-2]*stack[-1]
                stack = stack[:-2]
                stack.append(x)
            else:
                raiseOrReportError("Unknown formula %s" % struct.items(), 0, 4)

        if len(stack) == 1:
            ref,key = getRefKey(formula["output"])
            return ref,key,stack[0]
        else:
            raise DazError("Stack error %s" % stack)
            return None,None,0


    def evalFormulas(self, exprs, props, rig, mesh, useBone, useStages=False, verbose=False):
        success = False
        stages = []
        for formula in self.formulas:
            if self.evalFormula(formula, exprs, props, rig, mesh, useBone, useStages, stages):
                success = True
        if not success:
            if verbose:
                print("Could not parse formulas")
            return False
        return True


    def evalFormula(self, formula, exprs, props, rig, mesh, useBone, useStages, stages):
        from .bone import getTargetName

        driven = formula["output"].split("#")[-1]
        bname,channel = driven.split("?")
        if channel == "value":
            if False and mesh is None:
                if theSettings.verbosity > 3:
                    print("Cannot drive properties", bname)
                return False
            pb = None
        else:
            bname1 = getTargetName(bname, rig.pose.bones)
            if bname1 is None:
                print("Missing bone:", bname)
                return False
            else:
                bname = bname1
            if bname not in rig.pose.bones.keys():
                return False
            pb = rig.pose.bones[bname]

        path,idx,default = parseChannel(channel)
        if bname not in exprs.keys():
            exprs[bname] = {}
        if path not in exprs[bname].keys():
            if not useBone:
                value = default
            elif pb is None:
                value = Vector((default, default, default))
            else:
                try:
                    value = Matrix((default, default, default))
                    error = False
                except:
                    value = Matrix()
                    error = True
                if error:
                    raiseOrReportError("formula.py >> evalFormula()\n Failed to set value with default     \n %s" % default, 0, 3, False)
            exprs[bname][path] = {"value" : value, "prop" : None, "bone" : None}
        expr = exprs[bname][path]

        nops = 0
        type = None
        ops = formula["operations"]

        # URL
        struct = ops[0]
        if "url" not in struct.keys():
            return False
        prop,type = struct["url"].split("#")[-1].split("?")
        prop = prop.replace("%20", " ")
        path,comp,default = parseChannel(type)
        if type == "value":
            if props is None:
                return False
            expr["prop"] = prop
            props[prop] = True
        elif expr["bone"] is None:
            expr["bone"] = prop

        # Main operation
        last = ops[-1]
        op = last["op"]
        if op == "mult" and len(ops) == 3:
            if not useBone:
                if isinstance(expr["value"], Vector):
                    expr["value"][idx] = ops[1]["val"]
                else:
                    expr["value"] = ops[1]["val"]
            elif pb is None:
                expr["value"][comp] = ops[1]["val"]
            else:
                expr["value"][idx][comp] = ops[1]["val"]
        elif op == "push" and len(ops) == 1 and useStages:
            bone,string = last["url"].split(":")
            url,channel = string.split("?")
            asset = self.getAsset(url)
            if asset:
                stages.append((asset,bone,channel))
            else:
                msg = ("Cannot push asset:\n'%s'    " % last["url"])
                if theSettings.verbosity > 1:
                    print(msg)
        elif op == "spline_tcb":
            expr["points"] = [ops[n]["val"] for n in range(1,len(ops)-2)]
            expr["comp"] = comp
        else:
            #raiseOrReportError("Unknown formula %s" % ops, 3, 5, False)
            return False

        if "stage" in formula.keys() and len(stages) > 1:
            exprlist = []
            proplist = []
            for asset,bone,channel in stages:
                exprs1 = {}
                props1 = {}
                asset.evalFormulas(exprs1, props1, rig, mesh, useBone)
                if exprs1:
                    expr1 = list(exprs1.values())[0]
                    exprlist.append(expr1)
                if props1:
                    prop1 = list(props1.values())[0]
                    proplist.append(prop1)

            if formula["stage"] == "mult":
                self.multiplyStages(exprs, exprlist)
                #self.multiplyStages(props, proplist)

        return True


    def multiplyStages(self, exprs, exprlist):
        key = list(exprs.keys())[0]
        if exprlist:
            vectors = []
            for expr in exprlist:
                evalue = expr["value"]
                vectors.append(evalue["value"])
            struct = exprs[key] = exprlist[0]
            svalue = struct["value"]
            svalue["value"] = vectors


def getRefKey(string):
    base = string.split(":",1)[-1]
    return base.rsplit("?",1)


#-------------------------------------------------------------
#   Build bone formula
#   For bone drivers
#-------------------------------------------------------------

def buildBoneFormula(asset, rig, pbDriver, errors):
    from .driver import makeSimpleBoneDriver

    exprs = {}
    asset.evalFormulas(exprs, None, rig, None, True)

    for driven,expr in exprs.items():
        if driven not in rig.pose.bones.keys():
            continue
        pbDriven = rig.pose.bones[driven]
        if ("rotation" in expr.keys()):
            rot = expr["rotation"]["value"]
            driver = expr["rotation"]["bone"]
            if rot and driver in rig.pose.bones.keys():
                pbDriver = rig.pose.bones[driver]
                if pbDriver.parent == pbDriven:
                    print("Dependency loop: %s %s" % (pbDriver.name, pbDriven.name))
                else:
                    umat = convertDualMatrix(rot, pbDriver, pbDriven)
                    for idx in range(3):
                        makeSimpleBoneDriver(umat[idx], pbDriven, "rotation_euler", rig, driver, idx)

#-------------------------------------------------------------
#   Build shape formula
#   For corrective shapekeys
#-------------------------------------------------------------

def buildShapeFormula(asset, scn, rig, mesh):
    from .driver import makeSimpleBoneDriver, makeProductBoneDriver, makeSplineBoneDriver
    from .bone import BoneAlternatives

    if mesh is None or mesh.data.shape_keys is None:
        return

    exprs = {}
    props = {}
    if not asset.evalFormulas(exprs, props, rig, mesh, True, useStages=True, verbose=True):
        return False

    for sname,expr in exprs.items():
        if sname in rig.data.bones.keys():
            continue
        elif sname not in mesh.data.shape_keys.key_blocks.keys():
            print("No such shapekey:", sname)
            return False
        skey = mesh.data.shape_keys.key_blocks[sname]
        if "value" in expr.keys():
            value = expr["value"]
            bname = value["bone"]
            if bname is None:
                continue
            if bname not in rig.pose.bones.keys():
                if bname in BoneAlternatives.keys():
                    bname = BoneAlternatives[bname]
                else:
                    print("Missing bone:", bname)
                    continue
            pb = rig.pose.bones[bname]

            if "comp" in value.keys():
                j = value["comp"]
                points = value["points"]
                n = len(points)
                if (points[0][0] > points[n-1][0]):
                    points.reverse()

                diff = points[n-1][0] - points[0][0]
                vec = Vector((0,0,0))
                vec[j] = 1/(diff*D)
                uvec = convertDualVector(vec, pb, False)
                xys = []
                for k in range(n):
                    x = points[k][0]/diff
                    y = points[k][1]
                    xys.append((x, y))
                makeSplineBoneDriver(uvec, xys, skey, "value", rig, bname, -1)
            elif isinstance(value["value"], list):
                uvecs = []
                for vec in value["value"]:
                    uvec = convertDualVector(vec/D, pb, False)
                    uvecs.append(uvec)
                makeProductBoneDriver(uvecs, skey, "value", rig, bname, -1)
            else:
                vec = value["value"]
                uvec = convertDualVector(vec/D, pb, False)
                makeSimpleBoneDriver(uvec, skey, "value", rig, bname, -1)
    return True


Units = [
    Euler((1,0,0)).to_matrix(),
    Euler((0,1,0)).to_matrix(),
    Euler((0,0,1)).to_matrix()
]

def convertDualVector(uvec, pb, invert):
    from .node import getTransformMatrix
    smat = getTransformMatrix(pb)
    if invert:
        smat.invert()
    nvec = Vector((0,0,0))
    for i in range(3):
        mat = Mult3(smat, Units[i], smat.inverted())
        euler = mat.to_euler(pb.DazRotMode)
        nvec[i] = uvec.dot(Vector(euler))
    return nvec


def convertDualMatrix(umat, pbDriver, pbDriven):
    from .node import getTransformMatrix
    smat = getTransformMatrix(pbDriver)
    tmat = getTransformMatrix(pbDriven)
    nmat = Matrix().to_3x3()
    nmat.zero()

    for i in range(3):
        imat = Mult3(tmat, Units[i], tmat.inverted())
        ivec = Vector(imat.to_euler(pbDriven.DazRotMode))
        for j in range(3):
            jmat = Mult3(smat, Units[j], smat.inverted())
            jvec = Vector(jmat.to_euler(pbDriver.DazRotMode))
            nmat[i][j] = ivec.dot(Mult2(umat, jvec))
    return nmat

#-------------------------------------------------------------
#   Build prop formula
#   For prop drivers
#-------------------------------------------------------------

def buildPropFormula(asset, scn, rig, type, prefix, errors):
    from .bone import getTargetName
    from .driver import setFloatProp, setBoolProp
    from .transform import Transform

    exprs = {}
    props = {}
    asset.evalFormulas(exprs, props, rig, None, False)

    if not props:
        if theSettings.verbosity > 3:
            print("Cannot evaluate formula")
        if theSettings.verbosity > 4:
            print(asset.formulas)

    propmap = {}
    for prop in props.keys():
        propmap[prop] = prop
    for prop in exprs.keys():
        propmap[prop] = prop

    if prefix:
        from .morphing import propFromName
        nprops = {}
        for prop,value in props.items():
            nprop = propFromName(prop, type, prefix, rig)
            nprops[nprop] = value
            propmap[prop] = nprop
        for prop in exprs.keys():
            nprop = propFromName(prop, type, prefix, rig)
            propmap[prop] = nprop
        props = nprops

    # By default, use 0.0 for value and the configured min and max (usually -1.0...1.0) for sliders
    value = 0.0
    min = max = None

    # If useDazPropLimits is set: load default value, min and max from the asset
    if theSettings.useDazPropLimits and asset is not None:
        value = asset.value
        min = asset.min
        max = asset.max

    for prop in props.keys():
        if prop not in rig.keys():
            setFloatProp(rig, prop, value, min=min, max=max)
            setBoolProp(rig, "DzA"+prop, True)

    success = False
    for bname,expr in exprs.items():
        if rig.data.DazExtraFaceBones or rig.data.DazExtraDrivenBones:
            dname = bname + "Drv"
            if dname in rig.pose.bones.keys():
                bname = dname

        bname1 = getTargetName(bname, rig.pose.bones)
        if bname1 is None:
            key = propmap[expr["value"]["prop"]]
            prop = propmap[bname]
            dform = getNewFormula(rig, key, prop)
            dform.value = expr["value"]["value"]
            if dform.prop in [key+"L", key+"R"]:
                print("  ->", key[3:], dform.prop[3:], dform.value)
                addToStringGroup(rig.DazHiddenProps, key)
            if dform.value < 0:
                setFloatProp(rig, key, -value, min=-max, max=max)
            continue
        bname = bname1

        pb = rig.pose.bones[bname]
        tfm = Transform()
        nonzero = False
        if "translation" in expr.keys():
            tfm.setTrans(expr["translation"]["value"], propmap[expr["translation"]["prop"]])
            nonzero = True
        if "rotation" in expr.keys():
            tfm.setRot(expr["rotation"]["value"], propmap[expr["rotation"]["prop"]])
            nonzero = True
        if "scale" in expr.keys():
            tfm.setScale(expr["scale"]["value"], propmap[expr["scale"]["prop"]])
            nonzero = True
        if "general_scale" in expr.keys():
            tfm.setGeneral(expr["general_scale"]["value"], propmap[expr["general_scale"]["prop"]])
            nonzero = True
        if nonzero:
            # Fix: don't assume that the rest pose is at slider value 0.0.
            # For example: for 'default pose' (-1.0...1.0, default 1.0), use 1.0 for the rest pose, not 0.0.
            default = value if theSettings.useDazPropDefault else 0.0
            if addPoseboneDriver(scn, rig, pb, tfm, type, errors, default=default):
                success = True

    if success:
        return props
    else:
        return []


def getNewFormula(rig, key, prop):
    for item in rig.DazFormulas:
        if (item.key == key and
            item.prop == prop):
            return item
    item = rig.DazFormulas.add()
    item.key = key
    item.prop = prop
    return item


def getOldFormula(rig, key, prop):
    for item in rig.DazFormulas:
        if (item.key == key and
            item.prop == prop):
            return item
    return None


def inStringGroup(items, string):
    for item in items:
        if item.s == string:
            return True
    return False


def addToStringGroup(items, string):
    if inStringGroup(items, string):
        return
    item = items.add()
    item.s = string


def addPoseboneDriver(scn, rig, pb, tfm, type, errors, default=0.0):
    from .node import getBoneMatrix
    mat = getBoneMatrix(tfm, pb)
    loc,quat,scale = mat.decompose()
    scale -= Vector((1,1,1))
    success = False
    if (tfm.transProp and loc.length > 0.01*rig.DazScale):
        setFcurves(scn, rig, pb, "", loc, tfm.transProp, "location", type, errors, default)
        success = True
    if tfm.rotProp:
        if Vector(quat.to_euler()).length < 1e-4:
            pass
        elif pb.rotation_mode == 'QUATERNION':
            value = Vector(quat)
            value[0] = 1.0 - value[0]
            setFcurves(scn, rig, pb, "1.0-", value, tfm.rotProp, "rotation_quaternion", type, errors, default)
            success = True
        else:
            value = mat.to_euler(pb.rotation_mode)
            setFcurves(scn, rig, pb, "", value, tfm.rotProp, "rotation_euler", type, errors, default)
            success = True
    if (tfm.scaleProp and scale.length > 1e-4):
        setFcurves(scn, rig, pb, "", scale, tfm.scaleProp, "scale", type, errors, default)
        success = True
    elif tfm.generalProp:
        setFcurves(scn, rig, pb, "", scale, tfm.generalProp, "scale", type, errors, default)
        success = True
    return success


def setFcurves(scn, rig, pb, init, value, prop, channel, type, errors, default=0.0):
    from .daz import addCustomDriver
    path = '["%s"]' % prop
    key = channel[0:3].capitalize()
    fcurves = getBoneFcurves(rig, pb, channel)
    if len(fcurves) == 0:
        return
    if hasattr(fcurves[0].driver, "use_self"):
        for fcu in fcurves:
            idx = fcu.array_index
            addCustomDriver(fcu, rig, pb, init, value[idx], prop, key, errors, default)
            init = ""
    else:
        fcurves = getBoneFcurves(rig, pb, channel)
        for fcu in fcurves:
            idx = fcu.array_index
            addScriptedDriver(fcu, rig, pb, init, value[idx], path, errors)
            init = ""

#-------------------------------------------------------------
#   Eval formulas
#   For all kinds of drivers
#-------------------------------------------------------------

def parseChannel(channel):
    if channel == "value":
        return channel, 0, 0.0
    elif channel  == "general_scale":
        return channel, 0, 1.0
    attr,comp = channel.split("/")
    idx = getIndex(comp)
    if attr in ["rotation", "translation", "scale", "center_point", "end_point"]:
        default = Vector((0,0,0))
    elif attr in ["orientation"]:
        return None, 0, Vector()
    else:
        msg = ("Unknown attribute: %s" % attr)
        reportError(msg)
    return attr, idx, default


def getBoneFcurves(rig, pb, channel):
    if channel[0] == "[":
        dot = ""
    else:
        dot = "."
    path = 'pose.bones["%s"]%s%s' % (pb.name, dot, channel)
    fcurves = []
    if rig.animation_data:
        for fcu in rig.animation_data.drivers:
            if path == fcu.data_path:
                fcurves.append((fcu.array_index, fcu))
    if fcurves:
        return [data[1] for data in fcurves]
    else:
        try:
            return pb.driver_add(channel)
        except TypeError:
            return []


def addError(err, prop, pb, errors):
    if err not in errors.keys():
        errors[err] = {"props" : [], "bones": []}
    if prop not in errors[err]["props"]:
        errors[err]["props"].append(prop)
    if pb.name not in errors[err]["bones"]:
        errors[err]["bones"].append(pb.name)


def addScriptedDriver(fcu, rig, pb, init, value, path, errors):
    fcu.driver.type = 'SCRIPTED'
    var,isnew = getDriverVar(path, fcu.driver)
    if var is None:
        addError("Too many variables for the following properties:", path, pb, errors)
        return
    drvexpr = removeInitFromExpr(var, fcu.driver.expression, init)
    if abs(value) > 1e-4:
        if isnew:
            addDriverVar(var, path, fcu.driver, rig)
        if value < 0:
            sign = "-"
            value = -value
        else:
            sign = "+"
        expr = "%s%d*%s" % (sign, int(1000*value), var)
        drvexpr = init + "(" + drvexpr + expr + ")/1000"
        if len(drvexpr) <= 255:
            fcu.driver.expression = drvexpr
        else:
            string = drvexpr[0:249]
            string1 = string.rsplit("+",1)[0]
            string2 = string.rsplit("-",1)[0]
            if len(string1) > len(string2):
                string = string1
            else:
                string = string2
            drvexpr = string + ")/1000"
            fcu.driver.expression = drvexpr
            addError("Drive expression too long:", path, pb, errors)
            return

    if len(fcu.modifiers) > 0:
        fmod = fcu.modifiers[0]
        fcu.modifiers.remove(fmod)


def removeInitFromExpr(var, expr, init):
    import re
    expr = expr[len(init):]
    string = expr.replace("+"," +").replace("-"," -")
    words = re.split(' ', string[1:-6])
    nwords = [word for word in words if (word and var not in word)]
    return "".join(nwords)


def getDriverVar(path, drv):
    n1 = ord('A')-1
    for var in drv.variables:
        trg = var.targets[0]
        if trg.data_path == path:
            return var.name, False
        n = ord(var.name[0])
        if n > n1:
            n1 = n
    if n1 == ord('Z'):
        var = "a"
    elif n1 == ord('z'):
        var = None
    else:
        var = chr(n1+1)
    return var,True


def addDriverVar(vname, path, drv, rig):
    var = drv.variables.new()
    var.name = vname
    var.type = 'SINGLE_PROP'
    trg = var.targets[0]
    trg.id_type = 'OBJECT'
    trg.id = rig
    trg.data_path = path


def deleteRigProperty(rig, prop):
    if prop in rig.keys():
        del rig[prop]
    if hasattr(bpy.types.Object, prop):
        delattr(bpy.types.Object, prop)

