# Copyright (C) 2016 by David W. Jeske and donated to the public domain
#
#
# TODO:
#
#  - fix multiple drawing symbols "FAB" / "fab"
#  - add spline thickness 'radius' control, with taper
#  - add per-spline point "orientation" before rotate (for smoothed splines)
#  - make max_segments handle float, partially render last segment
#
# LATER TODO:
#  - add leaf turtle commands (generate leaf pos/orientation list)
#  - add more turtle commands (see Houdini docs)
#     - add symbol variables  F(1,2,3)
#     - add turtle command paramaters
#
#     http://archive.sidefx.com/docs/houdini10.0/nodes/sop/lsystem
#     https://github.com/ento/blender-lsystem-addon
#
# Here are the implemented operators, inspired by Houdini and the blender lsystem addon
#
#    F,A,B  draw forward
#    f,a,b  move forward without drawing
#    X,Y,Z,x,y,z do nothing
#    +, -   rotate around the forward axis (y - roll)
#    /, \   rotate around the up axis (z - yaw)
#    &, ^   rotate around the right axis (x - pitch)
#    [, ]   push/pop stack
#
# Here are some ideas to implement from the existing blender Lsystem addon
#
#    (, ) push/pop alterative stack
#    !, @ expand/srhink turtle stride
#    #, % fatten/slink mesh radius
#    ^, * greatly expand/srhink turtle stride
#    =, | greatly fatten/slink mesh radius

import math, re, random
from math import radians

import bpy
import mathutils
from bpy.props import *
from ... events import executionCodeChanged
from ... tree_info import keepNodeLinks
from ... utils.layout import writeText
from ... base_types.node import AnimationNode
from ... data_structures.splines.poly_spline import PolySpline

lsystemPresetItems = [
    ("KOCH_CURVE", "Koch Curve 2D", ""),
    ("SIERP_TRI", "Sierpinski triangle 2D", ""),
#    ("FRACT_PLNT", "Fractal Plant 2D", ""),
    ("HILBERT_C", "Hilbert Curve 2D", ""),
    ("CHAOT_SQR", "Chaotic Squares", ""),
    ("TREE_1", "Tree 1", ""),    
    ("CUSTOM", "Custom", ""),
 ]

baseDefaultValues = {
	"num_generations" : 3.0,
    "rotation_angle" : 90.0,
    "axiom" : "F",    
    "rule_1" : "F=F+F-F-F+F", "rule_2" : "", "rule_3" : "", "rule_4" : "", "rule_5": "",
}

presetValues = {
	"KOCH_CURVE" : {
        "axiom" : "F",
        "rule_1" : "F=F+F-F-F+F",
        "rotation_angle" : 90,
        "num_generations" : 2.0,
	},
    "SIERP_TRI" : {
        "axiom" : "A",
        "rule_1" : "A=+B-A-B+", "rule_2" : "B=-A+B+A-",
        "rotation_angle" : 60,
        "num_generations" : 4.0,
    },
    "FRACT_PLNT": { 
        "axiom" : "A",
        "rule_1" : "A=F-[[A]+A]+F[+FA]-A",
        "rule_2" : "F=FF",
        "rotation_angle" : 25,
        "segment_length" : 0.1
    },
    "HILBERT_C" : { 
        "axiom" : "A",
        "rule_1" : "A=+BF-AFA-FB+",
        "rule_2" : "B=-AF+BFB+FA-",
        "rotation_angle" : 90,
    },
    "CHAOT_SQR" : { 
        "axiom" : "FFFa",
        "rule_1" : "a=F[+Fa][-^Fa]",
        "rotation_angle" : 90,
        "num_generations" : 5.0,
    },
    "TREE_1" : {
        "axiom" : "FFFA",
        "rule_1" : "A=[&FFFA]////[&FFFA]////[&FFFA]",
        "rotation_angle" : 30,
        "num_generations" : 4.0,
    },    
}


#####################################################################################################
# SplinesFromLSystemNode - Animation Node and UI
#
		
class SplinesFromLSystemNode(bpy.types.Node, AnimationNode):
    bl_idname = "an_SplinesFromLSystemNode"
    bl_label = "Splines from L-System"

    def presetChanged(self,info):
        if self.lsystemPreset != "CUSTOM":        
            self.generateSockets()
            executionCodeChanged(self,info)

    lsystemPreset = EnumProperty(
        name = "Preset", default = "KOCH_CURVE",
        items = lsystemPresetItems, update = presetChanged)

    errorMessage = StringProperty()

    def draw(self, layout):
        layout.prop(self, "lsystemPreset", text = "Preset")
        if self.errorMessage != "":
            layout.label(self.errorMessage, icon = "ERROR")

    def drawAdvanced(self, layout):
        writeText(layout,
"""L-System Rule Operators are:\n\n
F,A,B : Draw segment forward
f,a,b : Move Forward without drawing
X,Y,Z : No drawing result
x,y,z : no drawing result
+, - : rorate around forward axis (y - roll)
/, \ : rotate around up axis (z - yaw)
&, ^ : rotate around right axis (x - pitch)
[, ] : push/pop stack
Q,P    : reserved
""")


    def readDefault(self, property_id):
        base_value = baseDefaultValues[property_id]
        if self.lsystemPreset in presetValues and property_id in presetValues[self.lsystemPreset]:
            base_value = presetValues[self.lsystemPreset][property_id]
        return base_value

    def getInputById(self, id):
        for input in self.inputs:
            if input.identifier == id:
                return input
        return None


# This does not work for some reason
#
#    def setDefaults(self):    
#        print("load defaults for " + self.lsystemPreset)    
#        for k,v in baseDefaultValues.items():
#            self.getInputById(k).value = v
#        if self.lsystemPreset in presetValues.items():
#            for k,v in presetValues[self.lsystemPreset]:
#                self.getInputById(k).value = v
    
    
    def create(self):
        self.generateSockets()


    @keepNodeLinks
    def generateSockets(self):   
        self.inputs.clear()
        self.outputs.clear() 
        # (dataType, name, identifier, **kwargs)

        # rule inputs        
        self.newInput("String", "Axiom", "axiom").value=self.readDefault("axiom")
        self.newInput("String", "Rule 1", "rule_1").value = self.readDefault("rule_1")
        self.newInput("String", "Rule 2", "rule_2").value = self.readDefault("rule_2")
        self.newInput("String", "Rule 3", "rule_3").value = self.readDefault("rule_3")
        self.newInput("String", "Rule 4", "rule_4", hide = True).value = self.readDefault("rule_4")
        self.newInput("String", "Rule 5", "rule_5", hide = True).value = self.readDefault("rule_5")

        # visible inputs
        self.newInput("Float", "Num Generations", "num_generations").value = self.readDefault("num_generations")
        self.newInput("Float", "Segment Length", "segment_length").value = 1
        self.newInput("Float", "Rotation Angle", "rotation_angle", minValue=0.0, maxValue=360.0).value=self.readDefault("rotation_angle")  

        # hidden inputs
        self.newInput("Vector", "Initial Position", "initial_position", hide=True)
        self.newInput("Quaternion", "Initial Direction", "initial_direction", value=(0,0,1,0), hide=True)
        
        self.newInput("Integer", "Random Geometry Seed", "random_seed", hide=True)
        self.newInput("Float", "Random Scale", "random_scale", value=0.0, minValue=0.0, hide=True)
        self.newInput("Float", "Random Rotation", "random_rotation", value=0.0, minValue=0.0, hide=True)
        self.newInput("Integer", "Max Segments", "max_segments", value=0,minValue=0, hide=True)
        self.newInput("Integer", "Max Segments Error", "max_segments_error", value=10000, minValue=0, hide=True)        

        # outputs                      
        self.newOutput("Spline List", "Splines", "splines")
        self.newOutput("String", "L-System String", "lsystem_string", hide=True)
        self.newOutput("Generic List", "Point Pairs", "point_pairs", hide=True)        

    def getExecutionCode(self):
        yield "self.errorMessage = ''"
        yield "if self.lsystemPreset != 'CUSTOM':"
        yield "    if axiom != self.readDefault('axiom') or \\"
        yield "           rule_1 != self.readDefault('rule_1') or \\"
        yield "           rule_2 != self.readDefault('rule_2') or \\"
        yield "           rule_3 != self.readDefault('rule_3') or \\"
        yield "           rule_4 != self.readDefault('rule_4') or \\"
        yield "           num_generations != self.readDefault('num_generations') or \\"
        yield "           rotation_angle != self.readDefault('rotation_angle'):"
        yield "        self.lsystemPreset = 'CUSTOM'" 

        # define these empty in case there is an error...
        yield "splines = []"
        yield "point_pairs = []"

        isLinked = self.getLinkedOutputsDict()
        if not (isLinked["lsystem_string"] or isLinked["splines"] or isLinked["point_pairs"]):            
            return
        
        yield "lsystem_string,num_generations_remainder = self.generateLSystem(axiom, [rule_1,rule_2,rule_3,rule_4,rule_5], num_generations)"

        yield "turtle = self.createTurtle(random_seed)"
        yield "turtle.max_segments = max_segments"
        yield "turtle.max_segments_error = max_segments_error"
        yield "turtle.num_generations_remainder = num_generations_remainder"
        yield "turtle.segment_length = segment_length"
        yield "turtle.rotation_angle = rotation_angle"
        yield "turtle.random_scale = random_scale"
        yield "turtle.random_rotation = random_rotation" 


        yield "try:"
        yield "    (point_pairs, splines, remainder_string) = turtle.convert(lsystem_string,initial_position.copy(), initial_direction.copy())"
        yield "except Exception as e:"
        yield "    self.errorMessage = str(e)"
    
    def createTurtle(self, random_seed):
        return LS_Turtle(random_seed = random_seed)        

    def generateLSystem(self, axiom, rules_list, num_generations_f):
        # we need to generate the lsystem_string            
        rules_dict = self.makeRulesDictFromInputs(rules_list)

        # figure out how many whole generations, and if there is a partial generation
        (num_generations_remainder, num_generations_whole) = math.modf(num_generations_f)
        num_generations_int = int(num_generations_whole)
        if (num_generations_remainder > 0.0):
            num_generations_int += 1                

        outstring = LSystem_Eval(axiom,rules_dict,num_generations_int, num_generations_remainder)
        # print("generateLSystem = " + outstring)
        return outstring, num_generations_remainder
    
    def makeRulesDictFromInputs(self, rules_list):            
        rules_dict = {}
        for rule in rules_list:
            if rule == "": continue
            m = re.match("^(?P<key>[^=QP ]+)=(?P<rule>[^=QP]+)$",rule)
            if m is None:
                self.errorMessage = "Malformed Rule: '%s'" % (rule)
            else:
                rules_dict[m.group("key")] = m.group("rule")
        return rules_dict

#####################################################################################################
# Lsystem Evaluator
#

def LSystem_Eval(axiom, rules_dict, num_generations_int, num_generations_remainder):    
    def lsystem_iter(axiom, rules, i, num_generations_int, num_generations_remainder):
        output = []
        for cur_sym in axiom:
            if cur_sym in rules:
                insert_text = rules[cur_sym]
                # last generation, make some replacements for partial drawing
                if (i+1 == num_generations_int) and num_generations_remainder != 0.0:
                    if cur_sym not in "FAB":
                        # replace every occurance
                        insert_text = re.sub("[FAB]","P",insert_text)
                    else:
                        # retain one normal instance, so we only grow the "new" ones
                        insert_text = re.sub(cur_sym, "Q", insert_text, count=1)  # replace one with a placeholder "Q"
                        insert_text = re.sub("[FAB]", "P", insert_text)
                        insert_text = re.sub("Q", cur_sym, insert_text, count=1)  # put "Q" back to normal...                                            
                                                
                output.append(insert_text)                
            else:
                output.append(cur_sym)
        return "".join(output)

    
    outstring = axiom
    for i in range(0,num_generations_int):
        outstring = lsystem_iter(outstring,rules_dict,i, num_generations_int, num_generations_remainder)
    return outstring


#####################################################################################################
# Turtle Geometry Generator
#

class LS_Turtle:    
    def __init__(self, random_seed = 0):
        self.segment_count              = 0   
        self.num_generations_remainder  = 0
        self.max_segments               = 0
        self.max_segments_error         = 10000         
        self.random_scale               = 0
        self.random_rotation            = 0
        self.segment_length             = 1
        self.rotation_angle             = 1
        
        self.rnd = random.Random()
        self.rnd.seed(random_seed)
        
    # here we compute segment and angle lenghts, possibly with random variation
    def compute_segment_length(self):
        return self.segment_length * ( (self.rnd.random() * self.random_scale) + 1)
    def compute_rotation_angle(self):
        return self.rotation_angle * ( (self.rnd.random() * self.random_rotation) + 1)


    # convert() is the recursive parser which converts the turtle string into geometry
    def convert(self,l_string, pos, dir):
        geometry = []
        spline_list = []
        
        dir = dir.copy()
            
        while len(l_string) != 0 and (self.max_segments == 0 or self.segment_count < self.max_segments):

            if (self.segment_count > self.max_segments_error):
                raise Exception("max_segments_error limit reached (%d)" % self.max_segments_error)
                
            cur_sym = l_string[0]
            l_string = l_string[1:]          
        
            # "P" is the special partial last generation
            if cur_sym == "P":
                self.segment_count+=1
                delta = mathutils.Vector((0,0,-self.compute_segment_length() * self.num_generations_remainder ))
                delta.rotate(dir)
                geometry.append([pos, pos + delta])
                spline_list.append(PolySpline.fromLocations([pos, pos+delta]))
                pos = pos + delta
            # "FAB" letters draw forward             
            elif cur_sym in "FAB":
                self.segment_count+=1
                delta = mathutils.Vector((0,0,-self.compute_segment_length()))
                delta.rotate(dir)
                geometry.append([pos, pos + delta])
                spline_list.append(PolySpline.fromLocations([pos, pos+delta]))
                pos = pos + delta
                
            # "fab" move forward without drawing
            elif cur_sym in "fab":
                delta = mathutils.Vector((0,0,-self.compute_segment_length()))
                delta.rotate(dir)
                pos = pos + delta

            # +, - rotate around the forward axis (y - roll)
            elif (cur_sym == '+'):
                dir = dir * mathutils.Euler((0,radians(self.compute_rotation_angle()),0)).to_quaternion()
            elif (cur_sym == '-'):
                dir = dir * mathutils.Euler((0,radians(-self.compute_rotation_angle()),0)).to_quaternion()

            # /, \ rotate around the up axis (z - yaw)
            elif (cur_sym == '/'):
                dir = dir * mathutils.Euler((0,0,radians(self.compute_rotation_angle()))).to_quaternion()
            elif (cur_sym == '\\'):
                dir = dir * mathutils.Euler((0,0,radians(-self.compute_rotation_angle()))).to_quaternion()

            # &, ^ rotate around the right axis (x - pitch)
            elif (cur_sym == '&'):
                dir = dir * mathutils.Euler((radians(self.compute_rotation_angle()),0,0)).to_quaternion()
            elif (cur_sym == '^'):
                dir = dir * mathutils.Euler((radians(-self.compute_rotation_angle()),0,0)).to_quaternion()
                
            # [, ] push/pop stack
            elif (cur_sym == '['):
                old_dir = dir.copy()
                (geom, sp_list, remainder) = self.convert(l_string,pos,dir)
                geometry = geometry + geom
                spline_list = spline_list + sp_list
                l_string = remainder
                dir = old_dir
            elif (cur_sym == ']'):
                return (geometry, spline_list, l_string)

        return (geometry, spline_list, l_string)

