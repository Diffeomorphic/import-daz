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

# ---------------------------------------------------------------------------
#
# The purpose of this file is to make facial drivers work even if the
# import-daz add-on is not available. A typical situation might be if you send
# the blend file to an external rendering service.
#
# 1. Disable the import-daz add-on and press Save User Settings.
# 2. Open this file (runtime_stripped_27x.py) in a text editor window.
# 3. Enable the Register checkbox.
# 4. Run the script (Run Script)
# 5. Save the blend file.
# 6. Reload the blend file.
#
# Alternative method:
#
# 1. Put this file in a place where Blender 2.79 looks for add-ons.
# 2. Disable the import-daz add-on and press Save User Settings.
# 3. Enable this add-on and Save User Settings.
# 4. Load the blend file.
#
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
#
# This file is for Blender 2.79 and lower.
#
# ---------------------------------------------------------------------------

bl_info = {
    "name": "DAZ Importer Stripped Runtime System",
    "author": "Thomas Larsson",
    "version": (1,0,0),
    "blender": (2,79,0),
    "location": "",
    "description": "Stripped RTS that defines function used by drivers.",
    "warning": "",
    "wiki_url": "http://diffeomorphic.blogspot.se/p/daz-importer-version-14.html",
    "tracker_url": "https://bitbucket.org/Diffeomorphic/import-daz/issues?status=new&status=open",
    "category": "Runtime"}


import bpy
from bpy.props import *
from bpy.app.handlers import persistent


class DazPropGroup(bpy.types.PropertyGroup):
    index = IntProperty()
    prop = StringProperty()
    factor = FloatProperty()
    default = FloatProperty()

    def __repr__(self):
        return "<PropGroup %d %s %f %f>" % (self.index, self.prop, self.factor, self.default)


def evalMorphs(pb, idx, key):
    rig = pb.constraints[0].target
    props = pb.DazLocProps if key == "Loc" else pb.DazRotProps if key == "Rot" else pb.DazScaleProps
    return sum([pg.factor*(rig[pg.prop]-pg.default) for pg in props if pg.index == idx])


@persistent
def updateHandler(scn):
    global evalMorphs
    bpy.app.driver_namespace["evalMorphs"] = evalMorphs


def register():
    bpy.utils.register_class(DazPropGroup)
    bpy.types.PoseBone.DazLocProps = CollectionProperty(type = DazPropGroup)
    bpy.types.PoseBone.DazRotProps = CollectionProperty(type = DazPropGroup)
    bpy.types.PoseBone.DazScaleProps = CollectionProperty(type = DazPropGroup)

    bpy.app.driver_namespace["evalMorphs"] = evalMorphs
    bpy.app.handlers.load_post.append(updateHandler)


def unregister():
    bpy.utils.unregister_class(DazPropGroup)


if __name__ == "__main__":
    register()
