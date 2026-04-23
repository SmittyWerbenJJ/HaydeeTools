import os
import re
import bpy
from math import pi
from bpy.props import *
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper
from mathutils import Vector,Matrix,Quaternion
from ..HaydeeUtils import *

# --------------------------------------------------------------------------------
#  .dmesh exporter
# --------------------------------------------------------------------------------

class DMesh:
    def __init__(self):
        self.hashed_unique_uvs_pos:dict[int:dict]={}
        self.uvs_dict=[]
        self.base_uv_index=0
        self.base_vertex_index=0
        self.first_vertex_index=0
        self.first_uv_index=0
        self.vertex_map={}
        self.vertex_output=[]
        self.new_mesh_uvs=[]
        self.uvs_output=[]
        self.smooth_groups=()
        self.smooth_groups_tot=0
        self.material_index=0
        self.groups_output={}
        self.groups_count={}
        self.joints_output=[]
        self.weights_output=[]
        self.weights_count=0
        self.vertex_weights={}
        self.uvs_data:bpy.types.MeshUVLoop=None
        self.bone_indexes={}

    def loadObject(self,obj:bpy.types.Object,apply_modifiers:bool):
        depsgraph = bpy.context.evaluated_depsgraph_get()
        if apply_modifiers:
            self.ob_for_convert=obj.evaluated_get(depsgraph)
        else:
            self.ob_for_convert=obj.original

        self.mat:Matrix=obj.matrix_world
        self.mesh:bpy.types.Mesh=self.ob_for_convert.to_mesh()
        self.vertices=self.mesh.vertices
        self.materials=self.mesh.materials
        self.polygons=self.mesh.polygons


def func_export_mesh(operator,context,apply_modifiers,SELECTED_MATERIAL,ob:bpy.types.Object,dmesh:DMesh):
    """write mesh data in dmesh object"""
    settings = 'PREVIEW'
    # XXX TO MESH
    dmesh.loadObject(ob,apply_modifiers)

    material_index = -1
    dmesh.first_vertex_index = dmesh.base_vertex_index
    dmesh.first_uv_index = dmesh.base_uv_index

    if len(dmesh.mesh.uv_layers) >= 1:
        dmesh.uvs_data= dmesh.mesh.uv_layers[0].data
    else:
        dmesh.uvs_data = None

    uvs_data=dmesh.uvs_data
    dmesh.vertex_map={}
    dmesh.new_mesh_uvs = []

    for n in range(len(dmesh.vertices)):
        dmesh.vertex_map[n] = dmesh.base_vertex_index + n

    if uvs_data is not None:
        for n, uv in enumerate(uvs_data):
            uv_pos = uv.uv
            hashed_uv_pos=hashedN(uv_pos)
            if hashed_uv_pos in dmesh.hashed_unique_uvs_pos:
                idx = dmesh.hashed_unique_uvs_pos[hashed_uv_pos]["index"]

            else:
                idx = len(dmesh.hashed_unique_uvs_pos)
                dmesh.hashed_unique_uvs_pos[hashed_uv_pos] ={
                    "index":idx,
                    "coordinate":uv_pos
                }
                dmesh.new_mesh_uvs.append(uv_pos)
            dmesh.uvs_dict.append(idx)

        dmesh.base_uv_index += len(uvs_data)
    dmesh.base_vertex_index += len(dmesh.vertices)

    if len(dmesh.vertex_map) == 0:
        print("Ignoring mesh %s since no vertices found with material %s" % (ob.name, SELECTED_MATERIAL))
        return "continue"

    if uvs_data is None:
        operator.report({'ERROR'}, "Mesh " + ob.name + " is missing UV information")
        return "continue"
    dmesh.material_index=material_index
    return dmesh

def func_export_vertices(file_format:str,dmesh:DMesh):
    """write vertices data in dmesh object"""

    vertex_count = dmesh.base_vertex_index - dmesh.first_vertex_index
    print("Exporting %d vertices" % vertex_count)
    vertex_indexes = [0] * vertex_count
    for key, value in dmesh.vertex_map.items():
        vertex_indexes[value - dmesh.first_vertex_index] = key

    for index in vertex_indexes:
        v = dmesh.vertices[index]
        co = dmesh.mat @ v.co
        dmesh.vertex_output.append("\t\tvert %s %s %s;\n" % (d(-co.x), d(co.z), d(-co.y)))

    # Export UV map
    uv_count = dmesh.base_uv_index - dmesh.first_uv_index
    print("Exporting %d uvs" % uv_count)
    uv_indexes = [-1] * uv_count
    if len(dmesh.mesh.uv_layers) >= 1:
        for uv in dmesh.new_mesh_uvs:
            uv_coord = Vector(uv)
            if (file_format == 'H2'):
                uv_coord = Vector((uv_coord.x, 1-uv_coord.y))
            dmesh.uvs_output.append("\t\tuv %s %s;\n" % (d(uv_coord.x), d(uv_coord.y)))

    EXPORT_SMOOTH_GROUPS = False
    EXPORT_SMOOTH_GROUPS_BITFLAGS = True
    if (EXPORT_SMOOTH_GROUPS or EXPORT_SMOOTH_GROUPS_BITFLAGS):
        smooth_groups, smooth_groups_tot = dmesh.mesh.calc_smooth_groups(use_bitflags=EXPORT_SMOOTH_GROUPS_BITFLAGS)
        if smooth_groups_tot <= 1:
            smooth_groups, smooth_groups_tot = (), 0
    else:
        smooth_groups, smooth_groups_tot = (), 0
    dmesh.smooth_groups=smooth_groups
    dmesh.smooth_groups_tot=smooth_groups_tot

def func_export_faces(    SELECTED_MATERIAL,dmesh:DMesh):
    """ write faces data in dmesh object"""

    #Export faces (by material)
    current_material_index = -1
    if SELECTED_MATERIAL == '__ALL__':
        current_material_index += 1
        if dmesh.material_index != -1 and dmesh.material_index != current_material_index:
            return {"continue"}
        count = 0
        for polygon in dmesh.polygons:
            if polygon.material_index == current_material_index:
                count += 1
        if count == 0:
            return {"continue"}

        if len(dmesh.materials) > 1:
            group_name = dmesh.ob_for_convert.name + '_' + dmesh.materials[current_material_index].name
        else:
            group_name = dmesh.ob_for_convert.name

        regex = re.compile('^[0-9]')
        if regex.match(group_name):
            group_name = 'x' + group_name
        group_name = stripName(group_name)
        group_name = group_name[:NAME_LIMIT]
        #                if not group_name:
        #                    operator.report({'ERROR'}, "Mesh " + ob.name + ", no group name")
        #                    continue
        print("{} - {} faces".format(group_name,count))
        if group_name in dmesh.groups_output:
            group_output = dmesh.groups_output[group_name]
        else:
            group_output = []
            dmesh.groups_count[group_name] = 0

        for polygon in dmesh.polygons:
            if polygon.material_index == current_material_index:
                dmesh.groups_count[group_name] += 1
                group_output.append("\t\t\tface\n\t\t\t{\n")
                group_output.append("\t\t\t\tcount %d;\n" % len(polygon.vertices))
                group_output.append("\t\t\t\tverts ")
                for v in tuple(polygon.vertices)[::-1]:
                    group_output.append(" %d" % dmesh.vertex_map[v])
                group_output.append(";\n")
                if dmesh.uvs_data is not None:
                    group_output.append("\t\t\t\tuvs ")
                    for v in tuple(polygon.loop_indices)[::-1]:
                        group_output.append(" %d" % dmesh.uvs_dict[v + dmesh.first_uv_index])
                    group_output.append(";\n")
                if dmesh.smooth_groups_tot:
                    group_output.append("\t\t\t\tsmoothGroup %d;\n\t\t\t}\n" % dmesh.smooth_groups[polygon.index])
                else:
                    group_output.append("\t\t\t\tsmoothGroup %d;\n\t\t\t}\n" % 0)
        dmesh.groups_output[group_name] = group_output

    else:

        for mat in dmesh.materials:
            current_material_index += 1
            if dmesh.material_index != -1 and dmesh.material_index != current_material_index:
                return {"continue"}
            count = 0
            for polygon in dmesh.polygons:
                if polygon.material_index == current_material_index:
                    count += 1
            if count == 0:
                return {"continue"}

            if len(dmesh.materials) > 1:
                group_name = dmesh.ob_for_convert.name + '_' + mat.name
            else:
                group_name = dmesh.ob_for_convert.name
            regex = re.compile('^[0-9]')
            if regex.match(group_name):
                group_name = 'x' + group_name
            group_name = stripName(group_name)
            group_name = group_name[:NAME_LIMIT]

            #                    if not group_name:
            #                        operator.report({'ERROR'}, "Mesh " + ob.name + ", no group name")
            #                        continue

            print(group_name, 'count', count)
            if group_name in dmesh.groups_output:
                group_output = dmesh.groups_output[group_name]
            else:
                group_output = []
                dmesh.groups_count[group_name] = 0

            for polygon in dmesh.polygons:
                if polygon.material_index == current_material_index:
                    dmesh.groups_count[group_name] += 1
                    group_output.append("\t\t\tface\n\t\t\t{\n")
                    group_output.append("\t\t\t\tcount %d;\n" % len(polygon.vertices))
                    group_output.append("\t\t\t\tverts ")
                    for v in tuple(polygon.vertices)[::-1]:
                        group_output.append(" %d" % dmesh.vertex_map[v])
                    group_output.append(";\n")
                    if dmesh.uvs_data is not None:
                        group_output.append("\t\t\t\tuvs ")
                        for v in tuple(polygon.loop_indices)[::-1]:
                            group_output.append(" %d" % dmesh.uvs_dict[v + dmesh.first_uv_index])
                        group_output.append(";\n")
                    if dmesh.smooth_groups_tot:
                        group_output.append("\t\t\t\tsmoothGroup %d;\n\t\t\t}\n" % dmesh.smooth_groups[polygon.index])
                    else:
                        group_output.append("\t\t\t\tsmoothGroup %d;\n\t\t\t}\n" % 0)
            dmesh.groups_output[group_name] = group_output

    return {"group_name":group_name}

def func_export_skeleton(operator,dmesh:DMesh):
    """ write skeleton data in dmesh object"""
    armature=dmesh.ob_for_convert.find_armature()

    if not armature:
        return

    if armature.name != dmesh.ob_for_convert.find_armature().name:
        operator.report({'ERROR'}, "Multiple armatures present, please select only one")
        return

    print("Exporting armature: " + armature.name)

    armature = dmesh.ob_for_convert.find_armature()
    bones = armature.data.bones
    mat = armature.matrix_world

    dmesh.joints_output.append("\tjoints %d\n\t{\n" % len(bones))
    dmesh.bone_indexes = {}
    bone_index = 0
    r = Quaternion([0, 0, 1], -pi / 2)

    for bone in bones:
        head = mat @ bone.head.xyz
        q = bone.matrix_local.to_quaternion()
        q = q @ r
        dmesh.bone_indexes[bone.name[:NAME_LIMIT]] = bone_index
        bone_index += 1

        bone_name = boneRenameHaydee(bone.name)

        # print("Bone %s quaternion: %s" % (bone.name, bone.matrix.to_quaternion() @ r))
        dmesh.joints_output.append("\t\tjoint %s\n\t\t{\n" % bone_name)
        if bone.parent:
            parent_name = boneRenameHaydee(bone.parent.name)
            dmesh.joints_output.append("\t\t\tparent %s;\n" % parent_name)
            q = (bone.parent.matrix_local.to_3x3().inverted() @ bone.matrix_local.to_3x3()).to_quaternion()
            q = Quaternion([q.w, -q.y, q.x, q.z])
            #print("%s head: %s parent head: %s" % (bone.name[:NAME_LIMIT], bone.head, bone.parent.head_local))
            head = (mat @ bone.parent.matrix_local.inverted()).to_quaternion() @ (bone.head_local - bone.parent.head_local)
            head = Vector((-head.y, head.x, head.z))

        head = Vector((-head.x, -head.y, head.z))
        head = Vector((head.x, head.z, head.y))
        q = Quaternion([-q.w, q.x, -q.z, q.y])
        q = Quaternion([q.x, q.y, q.z, q.w])
        dmesh.joints_output.append("\t\t\torigin %s %s %s;\n" % (d(head.x), d(head.y), d(head.z)))
        dmesh.joints_output.append("\t\t\taxis %s %s %s %s;\n" % (d(q.w), d(q.x), d(q.y), d(q.z)))
        dmesh.joints_output.append("\t\t}\n")
    dmesh.joints_output.append("\t}\n")



    dmesh.vertex_weights = {}
    vertex_groups = dmesh.ob_for_convert.vertex_groups
    invalid_weighting = False
    for v in dmesh.vertices:
        for g in v.groups:
            group = vertex_groups[g.group]
            if not (group.name[:NAME_LIMIT] in dmesh.bone_indexes):
                continue
            bone = dmesh.bone_indexes[group.name[:NAME_LIMIT]]
            if v.index in dmesh.vertex_map:
                if g.weight > 0:
                    i = dmesh.vertex_map[v.index]
                    if not (i in dmesh.vertex_weights):
                        dmesh.vertex_weights[i] = []
                    dmesh.vertex_weights[i].append((dmesh.vertex_map[v.index], bone, g.weight))
    for i in sorted(dmesh.vertex_weights.keys()):
        weight_list = dmesh.vertex_weights[i]
        # sort bone names first?
        # weight_list = sorted(weight_list, key=lambda bw: bw[1], reverse=True)
        weight_list = sorted(weight_list, key=lambda bw: bw[2], reverse=True)
        # if len(weight_list) > 4:
        #    weight_list = weight_list[0:3]
        sum = 0
        for w in weight_list:
            sum += w[2]
        for w in weight_list:
            normalized_weight = w[2] / sum
            dmesh.weights_output.append("\t\tweight %d %d %s;\n" % (w[0], w[1], d(normalized_weight)))
            dmesh.weights_count += 1


def to_file(separate_files, filepath, group_name, dmesh:DMesh):
    """write dmesh object data to file"""

    if separate_files:
        folder_path, basename = (os.path.split(filepath))
        name, ext = (os.path.splitext(filepath))
        filepath = os.path.join(folder_path, "{}{}".format(group_name, ext))

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("HD_DATA_TXT 300\n\n")
        f.write("mesh\n{\n")
        f.write("\tverts %d\n\t{\n" % dmesh.base_vertex_index)
        f.write("".join(dmesh.vertex_output))
        f.write("\t}\n")
        f.write("\tuvs %d\n\t{\n" % len(dmesh.hashed_unique_uvs_pos))
        f.write("".join(dmesh.uvs_output))
        f.write("\t}\n")
        f.write("\tgroups %d\n\t{\n" % len(dmesh.groups_output))
        for name, contents in dmesh.groups_output.items():
            f.write("\t\tgroup %s %d\n\t\t{\n" % (name, dmesh.groups_count[name]))
            f.write("".join(contents))
            f.write("\t\t}\n")
        f.write("\t}\n")
        f.write("".join(dmesh.joints_output))
        if dmesh.weights_count > 0:
            f.write("\tweights %d\n\t{\n" % dmesh.weights_count)
            f.write("".join(dmesh.weights_output))
            f.write("\t}\n")
        f.write("}\n")


def write_dmesh(operator, context, filepath, export_skeleton,
                apply_modifiers, selected_only, separate_files,
                ignore_hidden, SELECTED_MATERIAL, file_format):

    print("Exporting mesh, material: %s" % SELECTED_MATERIAL)

    mesh_count = 0
    for ob in context.scene.objects:
        if ob.type == "MESH":
            if SELECTED_MATERIAL == '__ALL__':
                mesh_count += 1
            else:
                for n in range(len(ob.material_slots)):
                    if ob.material_slots[n].name == SELECTED_MATERIAL:
                        mesh_count += 1
                        break

    if selected_only:
        list = context.selected_objects
        if len(list) == 0:
            list = context.scene.objects
    else:
        list = context.scene.objects


    dmesh=DMesh()
    group_name = None

    for ob in sorted([x for x in list if x.type == 'MESH'], key=lambda ob: ob.name):
        if ob.type == "MESH":

            if ignore_hidden and ob.hide_viewport:
                continue

            if separate_files:
                dmesh=DMesh()

            export_mesh_result = func_export_mesh(operator,context,apply_modifiers,SELECTED_MATERIAL,ob,dmesh)
            if export_mesh_result == "continue":
                continue

            # NOTE Export vertices
            if func_export_vertices(file_format,dmesh) == "continue":
                continue

            # NOTE Export faces (by material)
            export_faces_return=func_export_faces(SELECTED_MATERIAL,dmesh)
            if "continue" in export_faces_return:
                continue

            elif "group_name" in export_faces_return:
                group_name=export_faces_return["group_name"]

            # NOTE Export skeleton
            if export_skeleton:
                func_export_skeleton(operator,dmesh)

            # clean up
            dmesh.ob_for_convert.to_mesh_clear()

        if separate_files:
            to_file(separate_files, filepath, group_name, dmesh)

    if not separate_files:
        if dmesh.base_vertex_index == 0 or not group_name:
            operator.report({'ERROR'}, "Nothing to export")
            return {'FINISHED'}

        to_file(separate_files, filepath, group_name, dmesh)

    operator.report({"INFO"}, f"Exported {group_name}")
    return {'FINISHED'}


class ExportHaydeeDMesh(Operator, ExportHelper):
    bl_idname = "haydee_exporter.dmesh"
    bl_label = "Export Haydee dmesh"
    bl_options = {'REGISTER'}
    filename_ext = ".dmesh"
    filter_glob: StringProperty(
        default="*.dmesh",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    file_format: file_format_prop

    selected_only: BoolProperty(
        name="Selected only",
        description=
        "Export only selected objects (if nothing is selected, full scene will be exported regardless of this setting)",
        default=True,
    )
    separate_files: BoolProperty(
        name="Export to Separate Files",
        description="Export each object to a separate file",
        default=False,
    )
    ignore_hidden: BoolProperty(
        name="Ignore hidden",
        description="Ignore hidden objects",
        default=True,
    )
    apply_modifiers: BoolProperty(
        name="Apply modifiers",
        description="Apply modifiers before exporting",
        default=True,
    )
    export_skeleton: BoolProperty(
        name="Export skeleton",
        description="Export skeleton and vertex weights",
        default=True,
    )
    material: EnumProperty(name="Material",
                           description="Material to export",
                           items=materials_list)

    def execute(self, context):
        return write_dmesh(self, context, self.filepath, self.export_skeleton,
                           self.apply_modifiers, self.selected_only,
                           self.separate_files, self.ignore_hidden,
                           self.material, self.file_format)
