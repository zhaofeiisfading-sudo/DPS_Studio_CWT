"""Repository-local paths; refuse links before any traversal or output creation."""

import hashlib
from pathlib import Path

ROOT = Path(__file__).absolute().parents[2]


def checked_path(path: Path, boundary: Path) -> Path:
    candidate = path.absolute()
    for ancestor in (candidate, *candidate.parents):
        if ancestor.is_symlink() or ancestor.is_junction():
            raise ValueError(f"link/reparse path refused: {ancestor}")
    candidate = candidate.resolve()
    if not candidate.is_relative_to(boundary.resolve()):
        raise ValueError(f"path outside allowed boundary: {candidate}")
    return candidate


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def scan_files(root: Path) -> list[Path]:
    checked_path(root, ROOT)
    files: list[Path] = []
    for child in sorted(root.iterdir()):
        checked_path(child, root)
        if child.is_dir():
            files.extend(scan_files(child))
        elif child.is_file():
            files.append(child)
    return files
