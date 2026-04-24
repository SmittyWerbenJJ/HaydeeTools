# <pep8 compliant>

"""Blender Addon. Haydee 1 & 2 importer/exporter."""

bl_info = {
    "name": "Haydee 1 & 2 I/O Scripts",
    "author": "johnzero7, Pooka, Kein,SmittyWerbenJJ",
    "version": (1, 4, 0),
    "blender": (4, 1, 0),
    "location": "File > Import-Export > HaydeeTools",
    "description": "Import-Export scripts for Haydee",
    "warning": "",
    "doc_url": "https://github.com/SmittyWerbenJJ/HaydeeTools",
    "tracker_url": "https://github.com/SmittyWerbenJJ/HaydeeTools/issues",
    "category": "Import-Export",
}

import bpy
from . import haydee_importer as HaydeeImporter
from . import haydee_exporter as HaydeeExporter
from . import HaydeePreferences
from .haydee_ui import haydee_ui as HaydeeUI
from . import HaydeeUtils
from . import addon_updater_ops

# Modules with register and unregister functions
modulesToRegister = [
    HaydeeUtils, HaydeePreferences, HaydeeUI, HaydeeImporter,HaydeeExporter
]
import zipfile
def register():
    """Register addon classes."""

    for cls in modulesToRegister:
        try:
            cls.unregister()
        except:pass

    for module in modulesToRegister:
        module.register()

    addon_updater_ops.register(bl_info)


def unregister():
    """Unregister addon classes."""
    for module in modulesToRegister:
        module.unregister()

    addon_updater_ops.unregister()
