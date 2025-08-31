#! /usr/bin/env python3

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional
from datetime import datetime


def get_block_content(block_id: str) -> list[str]:
    block_content_py = ""
    with open(f"build/blocks/{block_id}.txt", "r") as file:
        block_content_py = file.read()

    block_content_j2 = ""
    with open(f"build/blocks/{block_id}.j2", "r") as file:
        block_content_j2 = file.read()

    return [block_content_py, block_content_j2]

def get_git_branch():
    """Get the Git branch from Git."""
    try:
        result = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True)
        return result.stdout.strip()
    except Exception as e:
        print(f"Warning: Could not execute Git command: {e}")
        return "unknown"

def get_git_commit_hash():
    """Get the short commit hash from Git."""
    try:
        # Get the short commit hash (first 7 characters)
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            print(f"Warning: Could not get Git commit hash: {result.stderr}")
            return "unknown"
    except Exception as e:
        print(f"Warning: Could not execute Git command: {e}")
        return "unknown"

def main() -> None:
    src_dir = os.path.abspath("src")
    src_filename = "notifyslack.py"
    src_filepath = os.path.join(src_dir, src_filename)

    dist_dir = os.path.abspath("dist")
    dist_filename_tmp = f"{src_filename}.tmp"

    shutil.copy(src_filepath, os.path.join(dist_dir, dist_filename_tmp))

    dist_filepath_tmp = os.path.join(dist_dir, dist_filename_tmp)

    content = ""
    try:
        with open(dist_filepath_tmp, "r") as file:
            content = file.read()
    except FileNotFoundError:
        print(f"File {dist_filepath_tmp} not found")
        return
    
    dist_filename_py = src_filename
    dist_filename_j2 = f"{src_filename}.j2"

    dist_filepath_py = shutil.copy(dist_filepath_tmp, os.path.join(dist_dir, dist_filename_py))
    dist_filepath_j2 = shutil.copy(dist_filepath_tmp, os.path.join(dist_dir, dist_filename_j2))

     # Get full blocks with markers included
    block_list = []
    block_Re = re.compile(r"(?s)# BUILD::.*?::.*?\n.*?# BUILD::.*?::END", re.MULTILINE)
    block_id_re = re.compile(r"(?s)# BUILD::(.*?)::(.*?)")
    content_py = content
    content_j2 = content
    for match in block_Re.finditer(content):
        block = match.group(0)  # The entire match including markers
        block_list.append(block)
        block_line1 = block.splitlines()[0] if block.splitlines() else ""
        block_id = block_id_re.search(block_line1).group(1)
        if "REMOVE" in block_line1:
            content = content.replace(block, "")
            continue
        print(f"Block ID: {block_id}")
        content = content.replace(block, block_line1)

        block_content_py, block_content_j2 = get_block_content(block_id)
        content_py = content_py.replace(block, block_content_py)
        content_j2 = content_j2.replace(block, block_content_j2)

    eof = "\n# Build information:"
    eof += f"\n# - branch: {get_git_branch()}"
    eof += f"\n# - commit: {get_git_commit_hash()}"
    eof += f"\n# - generated: {datetime.now().isoformat()}\n"
    content_py += eof
    content_j2 += eof

    with open(dist_filepath_py, "w") as file:
        file.write(content_py)
    with open(dist_filepath_j2, "w") as file:
        file.write(content_j2)

    os.unlink(dist_filepath_tmp)

    print(f"Successfully built {dist_filename_py} and {dist_filename_j2}")

if __name__ == "__main__":
    main()