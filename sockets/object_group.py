import bpy
from bpy.props import *
from .. events import propertyChanged
from .. base_types.socket import AnimationNodeSocket

class ObjectGroupSocket(bpy.types.NodeSocket, AnimationNodeSocket):
    bl_idname = "an_ObjectGroupSocket"
    bl_label = "Object Group Socket"
    dataType = "Object Group"
    allowedInputTypes = ["Object Group"]
    drawColor = (0.3, 0.1, 0.1, 0.8)

    groupName = StringProperty(update = propertyChanged)
    showName = BoolProperty(default = True)

    def drawInput(self, layout, node, text):
        if not self.showName: text = ""
        self.drawAsProperty(layout, text)

    def drawAsProperty(self, layout, text):
        layout.prop_search(self, "groupName", bpy.data, "groups", text = text)

    def getValue(self):
        return bpy.data.groups.get(self.groupName)

    def setStoreableValue(self, data):
        self.groupName = data

    def getStoreableValue(self):
        return self.groupName