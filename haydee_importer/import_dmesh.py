from math import pi
import os
import bpy
from bpy.types import Operator
from bpy.props import *
from bpy_extras.io_utils import ImportHelper
import io
from mathutils import Matrix, Quaternion, Vector
from ..HaydeeUtils import *

# --------------------------------------------------------------------------------
# .dmesh importer
# --------------------------------------------------------------------------------


def recurBonesOriginMesh(progress, parentBone, jointNames, jointAxis,
                         jointOrigin):
    for childBone in parentBone.children:
        if childBone:
            idx = jointNames.index(childBone.name)
            mat = Quaternion(jointAxis[idx]).to_matrix().to_4x4()
            pos = Vector(jointOrigin[idx])

            # INV row
            x1 = Matrix(
                ((-1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))
            # INV col
            x2 = Matrix(
                ((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))

            mat = parentBone.matrix @ (x1 @ mat @ x2)
            pos = parentBone.matrix @ Vector((-pos.z, pos.x, pos.y))
            mat.translation = pos
            childBone.matrix = mat

            recurBonesOriginMesh(progress, childBone, jointNames, jointAxis,
                                 jointOrigin)
            progress.step()


def read_dmesh(operator, context, filepath, file_format):
    print('dmesh:', filepath)
    with ProgressReport(context.window_manager) as progReport:
        with ProgressReportSubstep(progReport, 4, "Importing dmesh",
                                   "Finish Importing dmesh") as progress:
            if (bpy.context.mode != 'OBJECT'):
                bpy.ops.object.mode_set(mode='OBJECT')

            bpy.ops.object.select_all(action='DESELECT')
            print("Importing dmesh: %s" % filepath)

            basename = os.path.basename(filepath)
            collName = os.path.splitext(basename)[0]
            collection = createCollection(collName)
            setActiveCollection(collName)

            vert_data = None
            uv_data = None
            face_data = None

            progress.enter_substeps(1, "Read file")
            data = None
            encoding = find_encoding(filepath)
            with open(filepath, "r", encoding=encoding) as a_file:
                data = io.StringIO(a_file.read())
            progress.leave_substeps("Read file end")

            line = stripLine(data.readline())
            line_split = line.split()
            line_start = line_split[0]
            signature = line_start

            print('Signature:', signature)
            if signature != 'HD_DATA_TXT':
                print("Unrecognized signature: %s" % signature)
                operator.report({'ERROR'}, "Unrecognized file format")
                return {'FINISHED'}

            level = 0
            vert_data = []
            uv_data = []
            face_verts = []
            face_uvs = []
            smoothGroups = []
            vCount = None

            jointName = None
            jointNames = []
            jointOrigin = []
            jointAxis = []
            jointParents = []

            weights = []

            meshFaces = {}
            meshUvs = {}
            meshSmoothGroups = {}

            contextName = None
            meshName = None

            # steps = len(data.getvalue().splitlines()) - 1
            progress.enter_substeps(1, "Parse Data")
            # Read model data
            for lineData in data:
                line = stripLine(lineData)
                line_split = line.split()
                line_start = None
                i = len(line_split)
                if (i == 0):
                    continue
                line_start = line_split[0]
                if (line_start in ('{')):
                    level += 1
                if (line_start in ('}')):
                    level -= 1
                    contextName = None

                if (line_start == 'verts', 'face', 'joint'):
                    contextName = line_start

                # All verts
                if (line_start == 'vert'):
                    readVec(line_split, vert_data, 3, float)

                # All UVs
                if (line_start == 'uv'):
                    readVec(line_split, uv_data, 2, float)

                # Faces
                if (line_start == 'group' and level >= 2):
                    meshName = line_split[1]
                    meshFaces[meshName] = []
                    meshUvs[meshName] = []
                    meshSmoothGroups[meshName] = []

                if (line_start == 'count' and level >= 3):
                    vCount = int(line_split[1])
                if (line_start == 'verts' and level >= 3):
                    readVec(line_split, meshFaces[meshName], vCount, int)
                if (line_start == 'uvs' and level >= 3):
                    readVec(line_split, meshUvs[meshName], vCount, int)
                if (line_start == 'smoothGroup' and level >= 3):
                    meshSmoothGroups[meshName].append(int(line_split[1]))

                # Joints
                if (line_start == 'joint' and level >= 2):
                    jointName = line_split[1]
                    jointNames.append(jointName)
                    jointParents.append(None)
                if (line_start == 'parent' and level >= 3):
                    jointParents[len(jointParents) - 1] = line.split(' ', 1)[1]
                if (line_start == 'origin' and level >= 3):
                    readVec(line_split, jointOrigin, 3, float)
                if (line_start == 'axis' and level >= 3):
                    readVec(line_split, jointAxis, 4, float)

                # Joints (Vert, Bone, Weight)
                if (line_start == 'weight' and level >= 2):
                    readWeights(line_split, weights)
                # progress.step()
            progress.leave_substeps("Parse Data end")

            for idx, name in enumerate(jointNames):
                jointNames[idx] = boneRenameBlender(name)

            for idx, name in enumerate(jointParents):
                if name:
                    jointParents[idx] = boneRenameBlender(name)

            # create armature
            armature_ob = None
            if jointNames:
                boneCount = len(jointNames)
                progress.enter_substeps(boneCount, "Build armature")
                print('Importing Armature', str(boneCount), 'bones')

                armature_da = bpy.data.armatures.new(ARMATURE_NAME)
                # armature_da.display_type = 'STICK'
                armature_ob = bpy.data.objects.new(ARMATURE_NAME, armature_da)
                armature_ob.show_in_front = True

                linkToActiveCollection(armature_ob)
                bpy.context.view_layer.objects.active = armature_ob
                bpy.ops.object.mode_set(mode='EDIT')

                # create all Bones
                progress.enter_substeps(boneCount, "create bones")
                for idx, jointName in enumerate(jointNames):
                    editBone = armature_ob.data.edit_bones.new(jointName)
                    editBone.tail = Vector(editBone.head) + Vector((0, 0, 1))
                    progress.step()
                progress.leave_substeps("create bones end")

                # set all bone parents
                progress.enter_substeps(boneCount, "parenting bones")
                for idx, jointParent in enumerate(jointParents):
                    if (jointParent is not None):
                        editBone = armature_da.edit_bones[idx]
                        editBone.parent = armature_da.edit_bones[jointParent]
                    progress.step()
                progress.leave_substeps("parenting bones end")

                # origins of each bone is relative to its parent
                # recalc all origins
                progress.enter_substeps(boneCount, "aligning bones")
                rootBones = [
                    rootBone for rootBone in armature_da.edit_bones
                    if rootBone.parent is None
                ]
                for rootBone in rootBones:
                    idx = jointNames.index(rootBone.name)
                    mat = Quaternion(jointAxis[idx]).to_matrix().to_4x4()
                    pos = Vector(jointOrigin[idx])
                    mat.translation = vectorSwapSkel(pos)
                    rootBone.matrix = SWAP_ROW_SKEL @ mat @ SWAP_COL_SKEL
                    recurBonesOriginMesh(progress, rootBone, jointNames,
                                         jointAxis, jointOrigin)
                    progress.step()
                progress.leave_substeps("aligning bones end")

                # lenght of bones
                for bone in armature_da.edit_bones:
                    for child in bone.children:
                        center = child.head
                        proxVec = center - bone.head
                        boneVec = bone.tail - bone.head
                        norm = proxVec.dot(boneVec) / boneVec.dot(boneVec)
                        if (norm > 0.1):
                            proyVec = norm * boneVec
                            dist = (proxVec - proyVec).length
                            if (dist < 0.001):
                                bone.tail = center

                bpy.ops.object.mode_set(mode='OBJECT')
                progress.leave_substeps("Build armature end")

            if armature_ob:
                armature_ob.select_set(state=True)

            # Create mesh (verts and faces)
            progress.enter_substeps(len(meshFaces), "creating meshes")
            for meshName, face_verts in meshFaces.items():
                # face_verts = meshFaces[meshName]
                face_uvs = meshUvs[meshName]
                smoothGroups = meshSmoothGroups[meshName]

                progress.enter_substeps(1, "vertdic")
                vertDic = []
                for face in face_verts:
                    for vertIdx in face:
                        if vertIdx not in vertDic:
                            vertDic.append(vertIdx)
                progress.leave_substeps("vertdic end")

                # Obtain mesh exclusive verts and renumerate for faces
                progress.enter_substeps(1, "local verts")
                objVerts = [vert_data[oldIdx] for oldIdx in vertDic]
                objFaces = [
                    tuple(vertDic.index(oldIdx) for oldIdx in face)[::-1]
                    for face in face_verts
                ]
                progress.leave_substeps("local verts end")

                progress.enter_substeps(1, "mesh data")
                mesh_data = bpy.data.meshes.new(meshName)
                mesh_data.from_pydata(list(map(coordTransform, objVerts)), [],
                                      objFaces)
                # Shade smooth
                mesh_data.use_auto_smooth = True
                mesh_data.auto_smooth_angle = pi
                mesh_data.polygons.foreach_set("use_smooth", [True] *
                                               len(mesh_data.polygons))
                progress.leave_substeps("mesh data end")

                # apply UVs
                progress.enter_substeps(1, "uv")
                useUvs = True
                if useUvs and face_uvs is not None:
                    mesh_data.uv_layers.new()
                    blen_uvs = mesh_data.uv_layers[-1]
                    for idx, uvs in enumerate(
                        [uv for uvs in face_uvs for uv in uvs[::-1]]):
                        uv_coord = Vector(uv_data[int(uvs)])
                        if (file_format == 'H2'):
                            uv_coord = Vector((uv_coord.x, 1 - uv_coord.y))
                        blen_uvs.data[idx].uv = uv_coord
                progress.leave_substeps("uv end")

                useSmooth = True
                if useSmooth:
                    # unique_smooth_groups
                    unique_smooth_groups = {}
                    for g in set(smoothGroups):
                        unique_smooth_groups[g] = None

                    if unique_smooth_groups:
                        sharp_edges = set()
                        smooth_group_users = {
                            context_smooth_group: {}
                            for context_smooth_group in
                            unique_smooth_groups.keys()
                        }
                        context_smooth_group_old = -1

                    # detect if edge is used in faces with different Smoothing Groups
                    progress.enter_substeps(1, "detect smooth")
                    for idx, face_vert_loc_indices in enumerate(objFaces):
                        len_face_vert_loc_indices = len(face_vert_loc_indices)
                        context_smooth_group = smoothGroups[idx]
                        if unique_smooth_groups and context_smooth_group:
                            # Is a part of of a smooth group and is a face
                            if context_smooth_group_old is not context_smooth_group:
                                edge_dict = smooth_group_users[
                                    context_smooth_group]
                                context_smooth_group_old = context_smooth_group
                            prev_vidx = face_vert_loc_indices[-1]
                            for vidx in face_vert_loc_indices:
                                edge_key = (prev_vidx,
                                            vidx) if (prev_vidx
                                                      < vidx) else (vidx,
                                                                    prev_vidx)
                                prev_vidx = vidx
                                edge_dict[edge_key] = edge_dict.get(
                                    edge_key, 0) + 1
                    progress.leave_substeps("detect smooth end")

                    # Build sharp edges
                    progress.enter_substeps(1, "build sharp")
                    if unique_smooth_groups:
                        for edge_dict in smooth_group_users.values():
                            for key, users in edge_dict.items():
                                if users == 1:  # This edge is on the boundry of 2 groups
                                    sharp_edges.add(key)
                    progress.leave_substeps("build sharp end")

                    # Mark sharp edges
                    progress.enter_substeps(1, "mark sharp")
                    if unique_smooth_groups and sharp_edges:
                        for e in mesh_data.edges:
                            if e.key in sharp_edges:
                                e.use_edge_sharp = True
                        # mesh_data.show_edge_sharp = True
                    progress.leave_substeps("mark sharp end")

                progress.enter_substeps(1, "linking")
                # link data to new Object
                mesh_obj = bpy.data.objects.new(mesh_data.name, mesh_data)
                progress.leave_substeps("linking end")

                # Assign vertex weights
                progress.enter_substeps(1, "weights")
                if weights:
                    for w in [
                            weight for weight in weights
                            if weight[0] in vertDic
                    ]:
                        boneName = jointNames[w[1]]
                        armature_da = armature_ob.data
                        bone = armature_da.bones.get(boneName)
                        if bone:
                            vertGroup = mesh_obj.vertex_groups.get(boneName)
                            if not vertGroup:
                                vertGroup = mesh_obj.vertex_groups.new(
                                    name=boneName)
                            vertGroup.add([vertDic.index(w[0])], w[2],
                                          'REPLACE')
                progress.leave_substeps("weights end")

                # parenting
                progress.enter_substeps(1, "parent")
                if armature_ob:
                    # parent armature
                    mesh_obj.parent = armature_ob
                    # armature modifier
                    mod = mesh_obj.modifiers.new(type="ARMATURE",
                                                 name="Armature")
                    mod.use_vertex_groups = True
                    mod.object = armature_ob
                progress.leave_substeps("parent end")

                linkToActiveCollection(mesh_obj)
                mesh_obj.select_set(state=True)
                # scene.update()
                progress.step()
            progress.leave_substeps("creating meshes end")

    return {'FINISHED'}


class ImportHaydeeDMesh(Operator, ImportHelper):
    bl_idname = "haydee_importer.dmesh"
    bl_label = "Import Haydee DMesh (.dmesh)"
    bl_description = "Import a Haydee DMesh"
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext = ".dmesh"
    filter_glob: StringProperty(
        default="*.dmesh",
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
        for file in self.files:
            read_dmesh(self, context, os.path.join(self.directory, file.name),
                       self.file_format)
        return {"FINISHED"}
