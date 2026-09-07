from pathlib import Path


TEST_FILE_PATTERNS = [
    "test_*.py",
    "*_test.py",
]


def detect_tests(repo_path: Path) -> dict:

    test_files = []

    for path in repo_path.rglob("*.py"):

        if "test" in path.name.lower():
            test_files.append(str(path))

    test_directories = []

    for path in repo_path.rglob("*"):

        if path.is_dir() and "test" in path.name.lower():
            test_directories.append(str(path))

    return {
        "has_tests": bool(test_files or test_directories),
        "test_file_count": len(test_files),
        "test_directory_count": len(test_directories),
        "test_files": test_files,
    }