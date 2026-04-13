"""
build the project locally
"""

import os
import zipfile
from pathlib import Path
import shutil
from pathspec import GitIgnoreSpec
import argparse
import zipfile
import re

BLENDER_VERSION_STR="3.3"
DEPLOYEMENT_IGNORED_PATTERNS = [
        ".git",
        ".vscode",
        ".gitignore",
        "setup.cfg",
        "scripts",
        "requirements.txt"
        
    ]

def match_path(path, patterns):
    """ match a pattern """
    for pattern in patterns:
        if pattern in str(path):
            return True
    return False


def get_gitignore_entries(project_dir:str):
    """ get gitignore entries """
    ignored_patterns = []
    gitignore_path=Path(project_dir).joinpath(".gitignore")

    if not gitignore_path.exists():
        return ignored_patterns

    with open(project_dir.joinpath(".gitignore")) as f:
        for line in f:
            line=line.strip()
            empty_line=line==""
            invalid_line=any(line.startswith(x) for x in ["#","!"])
            if not (empty_line or invalid_line):
                ignored_patterns.append(line)

    return ignored_patterns

def clear_build_folder(project_dir:str):
    """ clear the build folder """
    if not Path(project_dir).exists():
        return

    build_dir=Path(project_dir).joinpath("build")
    for file in build_dir.glob("*"):
        if file.is_file():
            file.unlink()
        else:
            shutil.rmtree(file,ignore_errors=True)

    build_dir.mkdir(parents=True,exist_ok=True)

def make_archive(
    project_dir: Path,
    ignored_patterns: list[str],
):
    """make archive"""
    print("Packaging the addon ...")
    project_name = project_dir.name
    final_zip_path = project_dir.joinpath("build").joinpath(project_name + ".zip")

    # make archive
    with zipfile.ZipFile(str(final_zip_path), "w") as zfile:
        spec = GitIgnoreSpec.from_lines(ignored_patterns)
        
        filelist=list(map(project_dir.joinpath, spec.match_tree_files(project_dir,negate=True)))
        for i, file in enumerate(filelist):
            relative_path = file.relative_to(project_dir)
            if file.is_file():
                print(f"{i+1:3}/{len(filelist)}\t{relative_path}")
                zfile.write(str(file), arcname=project_name + "/" + str(relative_path))




def deploy_addon(deploy_dir:Path,project_dir: Path, blender_version=BLENDER_VERSION_STR):
    """copy to blender addons folder"""
    print(f"Deploying to \"{deploy_dir}\"")
    project_name = Path(project_dir).name
    # blender_addons_folder = Path(os.getenv("APPDATA")).joinpath(
    #     rf"Blender Foundation\Blender\{blender_version}\scripts\addons"
    # )
    final_zip_path = Path(project_dir).joinpath("build").joinpath(project_name + ".zip")
    dst_folder = deploy_dir.joinpath(project_name)

    if dst_folder.exists():
        try:
            shutil.rmtree(dst_folder)
        except Exception as e:
            print(f"{e}\n\n--------------------\nFailed to clear addon folder:")
            return

    dst_folder.mkdir(parents=True, exist_ok=True)
    zipfile.ZipFile(final_zip_path).extractall(deploy_dir)


def build():
    # project dir,assuming this script is located in Project/scripts/
    parser = argparse.ArgumentParser(description="Build the current project as a addon")
    parser.add_argument(
        "--clean",
        action="store_true",
        default=False,
        help="Clean the build folder before building",
    )
    parser.add_argument("--deploy",type=Path,metavar="dir",   help="Copy the addon to blender addons folder,Requires version argument")
    
    parser.add_argument(
        "--version",
        type=str,
        default=BLENDER_VERSION_STR,
        help="Blender version to deploy the addon, e.g. 3.6",
    )
    args = parser.parse_args()

    # assuming we are in Project/scripts/
    project_dir = Path(__file__).parent.parent

    deployement_ignored_patterns=DEPLOYEMENT_IGNORED_PATTERNS
    deployement_ignored_patterns += get_gitignore_entries(project_dir)
    
    if args.clean:
        clear_build_folder(project_dir)

    make_archive(project_dir, deployement_ignored_patterns)
    

    if args.deploy is not None:
        if not args.version:
            print("Please specify the blender version to deploy the addon, e.g. --version 3.6")
            return
        if not re.match(r"^\d+\.\d+$", args.version):
            print(f"Possibly wrong blender version format {args.version}\nAre you sure you want to continue? (y/n): ", end="")
            if input().lower() not in ["y", "yes"]:
                return
        deploy_addon(args.deploy,project_dir, args.version,)

    print("Done.")



build()
