import bpy
from bpy.props import *
from mathutils import Vector
from ... events import propertyChanged
from ... base_types.node import AnimationNode

class ProjectOnSpline(bpy.types.Node, AnimationNode):
    bl_idname = "mn_ProjectOnSpline"
    bl_label = "Project on Spline"

    inputNames = { "Spline" : "spline",
                   "Location" : "location" }

    outputNames = { "Position" : "position",
                    "Tangent" : "tangent",
                    "Parameter" : "parameter" }

    def settingChanged(self, context):
        self.outputs["Parameter"].hide = self.extended
        propertyChanged()

    extended = BoolProperty(
        name = "Extended Spline",
        description = "Project point on extended spline. If this is turned on the parameter is not computable.",
        update = settingChanged)

    def create(self):
        self.inputs.new("mn_SplineSocket", "Spline").showName = False
        self.inputs.new("mn_VectorSocket", "Location")
        self.outputs.new("mn_VectorSocket", "Position")
        self.outputs.new("mn_VectorSocket", "Tangent")
        self.outputs.new("mn_FloatSocket", "Parameter")

    def draw_buttons(self, context, layout):
        layout.prop(self, "extended", text = "Extended")

    def execute(self, spline, location):
        spline.update()
        if spline.isEvaluable:
            if self.extended:
                position, tangent = spline.projectExtended(location)
                parameter = 0.0
            else:
                parameter = spline.project(location)
                position = spline.evaluate(parameter)
                tangent = spline.evaluateTangent(parameter)
            return position, tangent, parameter
        else:
            return Vector((0, 0, 0)), Vector((0, 0, 0)), 0.0