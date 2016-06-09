# Copyright (C) 2016 by David W. Jeske and donated to the public domain
#

import math, re, random
from math import radians

import bpy
import mathutils
from bpy.props import *
from ... events import executionCodeChanged
from ... utils.layout import writeText
from ... base_types.node import AnimationNode
from ... data_structures.splines.poly_spline import PolySpline

lsystemPresetItems = [
    ("KOCH_CURVE", "Koch Curve", ""),
    ("SIERP_TRI", "Sierpinski triangle", ""),
    ("CUSTOM", "Custom", ""),
 ]

baseDefaultValues = {
	"num_generations" : 3,
	"segment_length" : 1,
    "rotation_angle" : 90,
    "axiom" : "F",    
    "rule_1" : "F=F+F-F-F+F", "rule_2" : "", "rule_3" : "", "rule_4" : "", "rule_5": "",
}

presetValues = {
	"KOCH_CURVE" : {
        "axiom" : "F",
        "rule_1" : "F=F+F-F-F+F",
        "rotation_angle" : 90,
	},
    "SIERP_TRI" : {
        "axiom" : "A",
        "rule_1" : "A=+B-A-B+", "rule_2" : "B=-A+B+A-",
        "rotation_angle" : 60,
    }
}


#####################################################################################################
# SplinesFromLSystemNode - Animation Node and UI
#
		
class SplinesFromLSystemNode(bpy.types.Node, AnimationNode):
    bl_idname = "an_SplinesFromLSystemNode"
    bl_label = "Splines from L-System"

    def presetChanged(self,info):        
        self.setDefaults()
        executionCodeChanged(self,info)

    lsystemPreset = EnumProperty(
        name = "Preset", default = "KOCH_CURVE",
        items = lsystemPresetItems, update = presetChanged)

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

    def setDefaults(self):    
        print("load defaults for " + self.lsystemPreset)    
        for k,v in baseDefaultValues.items():
            self.getInputById(k).value = v
        if self.lsystemPreset in presetValues.items():
            for k,v in presetValues[self.lsystemPreset]:
                self.getInputById(k).value = v
        self.update()
    
    def create(self):
        # (dataType, name, identifier, **kwargs)

        # rule inputs        
        self.newInput("String", "Axiom", "axiom")
        self.newInput("String", "Rule 1", "rule_1")
        self.newInput("String", "Rule 2", "rule_2")
        self.newInput("String", "Rule 3", "rule_3")
        self.newInput("String", "Rule 4", "rule_4", hide = True)
        self.newInput("String", "Rule 5", "rule_5", hide = True)

        # visible inputs
        self.newInput("Float", "Num Generations", "num_generations")
        self.newInput("Float", "Segment Length", "segment_length")      
        self.newInput("Float", "Rotation Angle", "rotation_angle", minValue=0.0, maxValue=360.0)  

        # hidden inputs
        self.newInput("Vector", "Initial Position", "initial_position", hide=True)
        self.newInput("Quaternion", "Initial Direction", "initial_direction", value=(0,0,1,0), hide=True)
        
        self.newInput("Integer", "Random Seed", "random_seed", hide=True)
        self.newInput("Float", "Random Scale", "random_scale", value=1.0, minValue=0.0, hide=True)
        self.newInput("Float", "Random Rotation", "random_rotation", value=1.0, minValue=0.0, hide=True)
        self.newInput("Integer", "Max Segments", "max_segments", value=0,minValue=0, hide=True)
        self.newInput("Integer", "Max Segments Error", "max_segments_error", value=10000, minValue=0, hide=True)        

        # outputs
        self.newOutput("Float", "Value", "value")                        
        self.newOutput("Spline List", "Splines", "splines")
        self.newOutput("String", "L-System String", "lsystem_string", hide=True)
        self.newOutput("Generic List", "Point Pairs", "point_pairs", hide=True)

        self.setDefaults()

    def draw(self, layout):
        layout.prop(self, "lsystemPreset", text = "Preset")

    def drawAdvanced(self, layout):
        writeText(layout,
"""L-System Rule Operators are:\n\n
F,A,B : Draw segment forward
f,a,b : Move Forward without drawing
+, - : rorate around forward axis (x - roll)
/, \ : rotate around up axis (z - yaw)
&, ^ : rotate around right axis (y - pitch)
[, ] : push/pop stack
""")

    def getExecutionCode(self):
        # if not in CUSTOM preset, and any inputs are changed or linked, switch to "CUSTOM" preset
        # if in CUSTOM preset, save the input values (in case we need to restore them later)
        
        isLinked = self.getLinkedOutputsDict()
        # if not (isLinked["lsystem_string"] or isLinked["splines"] or isLinked["point_pairs"]):
        #    return []
        print(isLinked)
        
        yield "lsystem_string,num_generations_remainder = self.generateLSystem(axiom, [rule_1,rule_2,rule_3,rule_4,rule_5], num_generations)"
        yield "splines = []"
        yield "point_pairs = []"
        yield "value = 5.0"

        yield "turtle = self.createTurtle(random_seed)"
        yield "turtle.max_segments = max_segments"
        yield "turtle.max_segments_error = max_segments_error"
        yield "turtle.num_generations_remainder = num_generations_remainder"
        yield "turtle.segment_length = segment_length"
        yield "turtle.rotation_angle = rotation_angle"
        yield "(curve, splines, remainder_string) = turtle.convert(lsystem_string,initial_position.copy(), initial_direction.copy())"
    
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
        print("num_generations_int = %d, %s" % (num_generations_int,rules_dict))        

        outstring = LSystem_Eval(axiom,rules_dict,num_generations_int, num_generations_remainder)
        print("generateLSystem = " + outstring)
        return outstring, num_generations_remainder
    
    def makeRulesDictFromInputs(self, rules_list):            
        rules_dict = {}
        for rule in rules_list:
            if rule == "": continue
            m = re.match("^(?P<key>[^= ]+)=(?P<rule>[^= ]+)$",rule)
            if m is None:
                raise Exception("Malformed Rule: " + rule)
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
                # last generation
                if (i+1 == num_generations_int) and num_generations_remainder != 0.0:
                    insert_text = insert_text.replace("F","P")                            
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
        self.max_segments_error         = 100000         
        self.random_scale_factor        = 0
        self.random_rotation_factor     = 0
        self.segment_length             = 1
        self.rotation_angle             = 1
        
        self.rnd = random.Random()
        self.rnd.seed(random_seed)
        
    def compute_segment_length(self):
        return self.segment_length * ( (self.rnd.random() * self.random_scale_factor) + 1)
    def compute_rotation_angle(self):
        return self.rotation_angle * ( (self.rnd.random() * self.random_rotation_factor) + 1)

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

            # upper case letters draw forward             
            elif cur_sym.isupper():
                self.segment_count+=1
                delta = mathutils.Vector((0,0,-self.compute_segment_length()))
                delta.rotate(dir)
                geometry.append([pos, pos + delta])
                spline_list.append(PolySpline.fromLocations([pos, pos+delta]))
                pos = pos + delta
                
            # lower case letters move forward without drawing
            elif cur_sym.islower():
                delta = mathutils.Vector((0,0,-self.compute_segment_length()))
                delta.rotate(dir)
                pos = pos + delta

            # +, - rotate around the forward axis (x - roll)
            elif (cur_sym == '+'):
                dir = dir * mathutils.Euler((radians(self.compute_rotation_angle()),0,0)).to_quaternion()
            elif (cur_sym == '-'):
                dir = dir * mathutils.Euler((radians(-self.compute_rotation_angle()),0,0)).to_quaternion()

            # /, \ rotate around the up axis (z - yaw)
            elif (cur_sym == '/'):
                dir = dir * mathutils.Euler((0,0,radians(self.compute_rotation_angle()))).to_quaternion()
            elif (cur_sym == '\\'):
                dir = dir * mathutils.Euler((0,0,radians(-self.compute_rotation_angle()))).to_quaternion()

            # &, ^ rotate around the right axis (y - pitch)
            elif (cur_sym == '&'):
                dir = dir * mathutils.Euler((0,radians(self.compute_rotation_angle()),0)).to_quaternion()
            elif (cur_sym == '^'):
                dir = dir * mathutils.Euler((0,radians(-self.compute_rotation_angle()),0)).to_quaternion()
                
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

