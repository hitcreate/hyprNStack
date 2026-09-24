#!/usr/bin/env python3
"""Stage a plugin build at an immutable, content-addressed path.

Never copy a build over a .so that a running compositor might have loaded.
This tool only stages; it never loads, unloads, reloads, or edits Hyprland.
"""

import argparse
import hashlib
import os
import pathlib
import shutil
import stat
import tempfile


def digest(path: pathlib.Path) -> str:
    hash_ = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            hash_.update(block)
    return hash_.hexdigest()


def stage(source: pathlib.Path, directory: pathlib.Path) -> pathlib.Path:
    if source.is_symlink() or not source.is_file():
        raise ValueError("source must be a regular file, not a symlink")
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("destination must be an existing directory, not a symlink")

    expected = digest(source)
    target = directory / f"nstackLayoutPlugin-{expected}.so"
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_file() or digest(target) != expected:
            raise ValueError(f"immutable target differs from build: {target}")
        return target

    fd, temporary = tempfile.mkstemp(
        prefix=".nstack-stage-", suffix=".so", dir=directory
    )
    try:
        with os.fdopen(fd, "wb") as output, source.open("rb") as input_:
            shutil.copyfileobj(input_, output)
            output.flush()
            os.fsync(output.fileno())
        if digest(pathlib.Path(temporary)) != expected or digest(source) != expected:
            raise ValueError("source changed while staging")
        os.chmod(temporary, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        try:
            os.link(temporary, target)  # atomic no-clobber publication
        except FileExistsError:
            if (
                target.is_symlink()
                or not target.is_file()
                or digest(target) != expected
            ):
                raise ValueError(
                    f"immutable target differs from build: {target}"
                ) from None
        return target
    finally:
        pathlib.Path(temporary).unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=pathlib.Path)
    parser.add_argument("directory", type=pathlib.Path)
    args = parser.parse_args()
    print(stage(args.source, args.directory))


if __name__ == "__main__":
    main()
