from math import pi
import bpy
from bpy.types import Operator
from bpy.props import *
from bpy_extras.io_utils import ImportHelper

import struct

import os

from mathutils import Vector
from ..HaydeeUtils import *

# --------------------------------------------------------------------------------
# .mesh importer
# --------------------------------------------------------------------------------


def read_mesh(operator, context, filepath, outfitName, file_format):
    print('Mesh:', filepath)
    with ProgressReport(context.window_manager) as progReport:
        with ProgressReportSubstep(progReport, 4, "Importing mesh",
                                   "Finish Importing mesh") as progress:
            if (bpy.context.mode != 'OBJECT'):
                bpy.ops.object.mode_set(mode='OBJECT')

            SIGNATURE_SIZE = 28
            CHUNK_SIZE = 48
            INIT_INFO = 32
            VERT_SIZE = 60
            FACE_SIZE = 12
            DEFAULT_MESH_NAME = os.path.splitext(os.path.basename(filepath))[0]
            if outfitName:
                DEFAULT_MESH_NAME = DEFAULT_MESH_NAME

            bpy.ops.object.select_all(action='DESELECT')
            print("Importing mesh: %s" % filepath)

            progress.enter_substeps(1, "Read file")
            data = None
            with open(filepath, "rb") as a_file:
                data = a_file.read()
            progress.leave_substeps("Read file end")

            (signature, chunkCount, totalSize) = \
                struct.unpack('20sII', data[0:SIGNATURE_SIZE])
            signature = decodeText(signature)
            print('Signature:', signature)
            if signature != 'HD_CHUNK':
                print("Unrecognized signature: %s" % signature)
                operator.report({'ERROR'}, "Unrecognized file format")
                return {'FINISHED'}

            offset = SIGNATURE_SIZE + (CHUNK_SIZE * chunkCount)
            (vertCount, loopCount, x1, y1, z1, x2, y2, z2) = \
                struct.unpack('II3f3f', data[offset:offset + INIT_INFO])

            posTop = Vector((-x1, z1, -y1))
            posBottom = Vector((-x2, z2, -y2))

            headerSize = SIGNATURE_SIZE + (CHUNK_SIZE * chunkCount) + INIT_INFO
            delta = headerSize

            vert_data = []
            uv_data = []
            normals = []

            for n in range(vertCount):
                offset = delta + (VERT_SIZE * n)
                (
                    x, y, z,
                    u, v,
                    vcolorR, vcolorG, vcolorB, vcolorA,
                    normX, normY, normZ,
                    tanX, tanY, tanZ,
                    bitanX, bitanY, bitanZ) = \
                    struct.unpack('3f2f4B9f', data[offset:offset + VERT_SIZE])
                vert = Vector((-x, -z, y))
                uv = Vector((u, v))
                norm = Vector((-normX, -normZ, normY))
                vert_data.append(vert)
                uv_data.append(uv)
                normals.append(norm)

            faceCount = loopCount // 3
            delta = headerSize + (VERT_SIZE * vertCount)
            face_data = []
            print('faceCount', faceCount)
            for n in range(faceCount):
                offset = delta + (FACE_SIZE * n)
                (v1, v2, v3) = struct.unpack('3I',
                                             data[offset:offset + FACE_SIZE])
                face = [v3, v2, v1]
                face_data.append(face)

            # Create Mesh
            progress.enter_substeps(1, "mesh data")
            mesh_data = bpy.data.meshes.new(DEFAULT_MESH_NAME)
            mesh_data.from_pydata(vert_data, [], face_data)
            # Shade smooth
            mesh_data.shade_smooth()
            progress.leave_substeps("mesh data end")

            # apply UVs
            progress.enter_substeps(1, "uv")
            useUvs = True
            if useUvs and uv_data is not None:
                mesh_data.uv_layers.new()
                blen_uvs = mesh_data.uv_layers[-1]
                for loop in mesh_data.loops:
                    uv_coord = Vector(uv_data[loop.vertex_index])
                    if (file_format == 'H2'):
                        uv_coord = Vector((uv_coord.x, 1 - uv_coord.y))
                    blen_uvs.data[loop.index].uv = uv_coord
            progress.leave_substeps("uv end")

            # normals
            use_edges = True
            mesh_data.validate(clean_customdata=False)
            mesh_data.update(calc_edges=use_edges)
            if normals:
                if len(normals) == len(mesh_data.vertices):
                    # Per-vertex → expand to per-loop
                    loop_normals = [normals[loop.vertex_index] for loop in mesh_data.loops]
                else:
                    # Already per-loop
                    loop_normals = normals
                
                mesh_data.normals_split_custom_set(loop_normals)

            mesh_obj = bpy.data.objects.new(mesh_data.name, mesh_data)
            linkToActiveCollection(mesh_obj)
            mesh_obj.select_set(state=True)
            bpy.context.view_layer.objects.active = mesh_obj

    return {'FINISHED'}


class ImportHaydeeMesh(Operator, ImportHelper):
    bl_idname = "haydee_importer.mesh"
    bl_label = "Import Haydee mesh (.mesh)"
    bl_description = "Import a Haydee Mesh"
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext = ".mesh"
    filter_glob: StringProperty(
        default="*.mesh",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    file_format: file_format_prop
    directory: StringProperty(subtype='DIR_PATH')
    files: CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        for filepath in self.files:
            read_mesh(self, context, self.directory + filepath.name, None,
                      self.file_format)
        return {"FINISHED"}
