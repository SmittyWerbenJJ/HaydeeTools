from enum import Enum,IntEnum
from mathutils import Matrix


# Global enum for asset type
class Signature(IntEnum):
    HD_CHUNK = 0
    HD_DATA_TXT = 1
    HD_DATA_TXT_BOM = 2
    HD_MOTION = 3


# Constants

ARMATURE_NAME = 'Skeleton'
HD_CHUNK = b'\x48\x44\x5F\x43\x48\x55\x4E\x4B'
HD_DATA_TXT = b'\x48\x44\x5F\x44\x41\x54\x41\x5F\x54\x58\x54'
HD_DATA_TXT_BOM = b'\xFF\xFE\x48\x00\x44\x00\x5F\x00\x44\x00\x41\x00\x54\x00\x41\x00\x5F\x00\x54\x00\x58\x00\x54\x00'
HD_MOTION = b'\x48\x44\x5F\x4D\x4F\x54\x49\x4F\x4E\x00'

# Swap matrix rows
SWAP_ROW_SKEL = Matrix(
    ((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
# Swap matrix cols
SWAP_COL_SKEL = Matrix(
    ((1, 0, 0, 0), (0, 0, -1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))
