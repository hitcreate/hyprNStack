"""Regression: an update must never overwrite an already-staged plugin file."""

import pathlib
import tempfile
import unittest

from scripts.stage_plugin import stage


class StagePluginTests(unittest.TestCase):
    def test_second_build_uses_a_new_path_and_preserves_the_first(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            builds = root / "builds"
            builds.mkdir()
            source = root / "plugin.so"
            source.write_bytes(b"version-one")
            first = stage(source, builds)
            self.assertEqual(first, stage(source, builds))
            source.write_bytes(b"version-two")
            second = stage(source, builds)
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_bytes(), b"version-one")
            self.assertEqual(second.read_bytes(), b"version-two")

    def test_corrupt_existing_target_is_rejected_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            source = root / "plugin.so"
            source.write_bytes(b"valid")
            target = stage(source, root)
            target.chmod(0o644)
            target.write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError, "immutable target differs"):
                stage(source, root)
            self.assertEqual(target.read_bytes(), b"corrupt")

    def test_symlink_source_and_target_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            source = root / "plugin.so"
            source.write_bytes(b"valid")
            symlink = root / "alias.so"
            symlink.symlink_to(source)
            with self.assertRaisesRegex(ValueError, "source must be a regular file"):
                stage(symlink, root)
            target = stage(source, root)
            target.unlink()
            target.symlink_to(source)
            with self.assertRaisesRegex(ValueError, "immutable target differs"):
                stage(source, root)


if __name__ == "__main__":
    unittest.main()
