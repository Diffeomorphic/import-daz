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
import math
from .node import Node
from .settings import theSettings

class Camera(Node):

    def __init__(self, fileref):
        Node.__init__(self, fileref)
        self.perspective = {}
        self.orthographic = {}
        self.channels = {}
        self.aspectRatio = 1.0


    def __repr__(self):
        return ("<Camera %s>" % (self.id))


    def parse(self, struct):
        Node.parse(self, struct)
        if "perspective" in struct.keys():
            self.perspective = struct["perspective"]
        elif "orthographic" in struct.keys():
            self.orthographic = struct["orthographic"]
        if "extra" in struct.keys():
            for estruct in struct["extra"]:
                if estruct["type"] == "studio_node_channels":
                    self.channels = estruct["channels"]


    def postTransform(self):
        from .settings import theSettings
        if theSettings.zup:
            ob = self.rna
            ob.rotation_euler[0] += math.pi/2


    def build(self, context, inst=None):
        if self.perspective:
            self.data = bpy.data.cameras.new(self.name)
            self.setCameraProps(self.perspective)
        elif self.orthographic:
            self.data = bpy.data.cameras.new(self.name)
            self.setCameraProps(self.orthographic)
        else:
            return None
        #print("Camera", self.data)
        self.buildChannels()
        Node.build(self, context, inst)


    def setCameraProps(self, props):
        camera = self.data
        for key,value in props.items():
            #print("Camera", key, value)
            if key == "znear" :
                camera.clip_start = value * theSettings.scale
            elif key == "zfar" :
                camera.clip_end = value * theSettings.scale
            elif key == "yfov" :
                pass
            elif key == "focal_length" :
                camera.lens = value
            elif key == "depth_of_field" :
                pass
            elif key == "focal_distance" :
                self.setFocusDist(camera, value * theSettings.scale * 0.1)
            elif key == "fstop" :
                self.setFStop(camera, value)
            else:
                print("Unknown camera prop: '%s' %s" % (key, value))


    def setFocusDist(self, camera, value):
        if bpy.app.version < (2,80,0):
            camera.dof_distance = value
        else:
            camera.dof.focus_distance = value


    def setFStop(self, camera, value):
        if bpy.app.version < (2,80,0):
            camera.gpu_dof.fstop = value
            camera.cycles.aperture_fstop = value
        else:
            camera.dof.aperture_fstop = value


    def buildChannels(self):
        from .asset import getCurrentValue
        from .utils import D

        camera = self.data
        camera.sensor_width = 64
        for data in self.channels:
            channel = data["channel"]
            key = channel["id"]
            value = channel["current_value"]
            if key == "Lens Shift X" :
                camera.shift_x = value * theSettings.scale
            elif key == "Lens Shift Y" :
                camera.shift_y = value * theSettings.scale
            elif key == "Focal Length":
                camera.lens = value         # in mm
            elif key == "Depth of Field":
                self.setFocusDist(camera, value * theSettings.scale * 0.1)
            elif key == "Frame Width":
                pass
                #camera.sensor_width = value
                #camera.sensor_height = self.aspectRatio * value
            elif key == "Aspect Ratio":
                self.aspectRatio = value[1]/value[0]
                #camera.sensor_height = self.aspectRatio * camera.sensor_width
            elif key == "Aperture Blades":
                if bpy.app.version < (2,80,0):
                    camera.gpu_dof.blades = value
                    camera.cycles.aperture_blades = value
                else:
                    camera.dof.aperture_blades = value
            elif key == "Aperture Blade Rotation":
                if bpy.app.version < (2,80,0):
                    camera.cycles.aperture_rotation = value*D
                else:
                    camera.dof.aperture_rotation = value*D

            elif key in ["Point At", "Renderable", "Visible", "Selectable", "Perspective",
                        "Render Priority", "Cast Shadows", "Pixel Size",
                        "Lens Stereo Offset", "Lens Radial Bias", "Lens Stereo Offset",
                        "Lens Distortion Type", "Lens Distortion K1", "Lens Distortion K2", "Lens Distortion K3", "Lens Distortion Scale",
                        "DOF", "Aperature", "Disable Transform", "Visible in Simulation",
                        "Lens Thickness", "Local Dimensions", "Dimension Preset", "Constrain Proportions",
                        "HeadlampMode", "Headlamp Intensity", "XHeadlampOffset", "YHeadlamp", "ZHeadlampOffset",
                        "Display Persistence", "Sight Line Opacity",
                        "Focal Point Scale", "FOV Color", "FOV Opacity", "FOV Length",
                        "DOF Plane Visibility", "DOF Plane Color",
                        "Visible in Viewport", 
                        "DOF Overlay Color", "DOF Overlay Opacity", "Near DOF Plane Visibility", "Far DOF Plane Visibility",
                        ]:
                #print("Unused", key, value)
                pass
            else:
                print("Unknown camera channel '%s' %s" % (key, value))
