import subprocess
import tempfile
import shutil
import os
from typing import List, Dict


def clone_repositories(
    repositories: List[dict],
    max_repos: int = 5
) -> Dict[str, str]:
    """
    Shallow clones the selected repositories into temporary system folders.

    Each repository should contain:
        {
            "name": "repository-name",
            "owner": "github-owner",
            "url": "https://github.com/github-owner/repository-name"
        }

    Returns:
        {
            "repository-name": "/path/to/cloned/folder"
        }
    """

    cloned_paths = {}

    for repository in repositories[:max_repos]:

        name = repository["name"]
        owner = (repository.get("owner") or {}).get("login")
        repo_url = repository["url"]

        # Create an isolated temporary folder
        temp_dir = tempfile.mkdtemp(
            prefix=f"gh_eval_{owner}_{name}_"
        )

        # Git clone expects the .git URL
        if not repo_url.endswith(".git"):
            clone_url = f"{repo_url}.git"
        else:
            clone_url = repo_url

        try:
            print(f"[Cloner] Cloning {owner}/{name}...")

            subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    clone_url,
                    temp_dir
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120
            )

            cloned_paths[name] = temp_dir

            print(
                f"[Cloner] Successfully cloned "
                f"{owner}/{name} -> {temp_dir}"
            )

        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired
        ) as err:

            print(
                f"[Cloner Error] Failed cloning "
                f"{owner}/{name}: {err}"
            )

            shutil.rmtree(
                temp_dir,
                ignore_errors=True
            )

    return cloned_paths


def cleanup_cloned_repos(repo_paths: Dict[str, str]):
    """
    Deletes all temporary folders after analysis
    to prevent disk leaks.
    """

    for name, path in repo_paths.items():

        if os.path.exists(path):

            shutil.rmtree(
                path,
                ignore_errors=True
            )

            print(
                f"[Cleanup] Removed temp folder for {name}"
            )