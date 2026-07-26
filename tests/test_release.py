import importlib.util
import unittest
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RELEASE_SCRIPT = PROJECT_ROOT / ".github" / "scripts" / "release.py"

spec = importlib.util.spec_from_file_location("release_script", RELEASE_SCRIPT)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ParseVersionTests(unittest.TestCase):
    def test_parses_standard_semver_tag(self):
        self.assertEqual(release.parse_version("v1.2.3"), (1, 2, 3))

    def test_rejects_non_semver_tags(self):
        invalid_tags = (
            "1.2.3",
            "v1.2",
            "v1.2.3-rc1",
            "v01.2.3",
            "version-1.2.3",
            "",
        )
        for tag in invalid_tags:
            with self.subTest(tag=tag):
                self.assertEqual(release.parse_version(tag), (0, 0, 0))

    def test_latest_tag_ignores_invalid_v_tags(self):
        tags = "vNext\nv2.1.0\nv2.0.0"
        with mock.patch.object(release, "run", return_value=tags) as run_mock:
            self.assertEqual(release.get_latest_tag(), "v2.1.0")
        run_mock.assert_called_once_with(
            ["git", "tag", "--merged", "HEAD", "--list", "v*", "--sort=-v:refname"]
        )

    def test_latest_tag_returns_empty_string_when_no_tags_exist(self):
        with mock.patch.object(release, "run", return_value=""):
            self.assertEqual(release.get_latest_tag(), "")


class DecideBumpTests(unittest.TestCase):
    def test_no_commits_means_no_release(self):
        self.assertEqual(release.decide_bump([]), "")

    def test_regular_feature_is_minor(self):
        self.assertEqual(release.decide_bump(["feat: nueva funcion"]), "minor")

    def test_scoped_feature_is_minor(self):
        self.assertEqual(release.decide_bump(["feat(ui): nueva funcion"]), "minor")

    def test_breaking_bang_without_scope_is_major(self):
        self.assertEqual(release.decide_bump(["feat!: cambio incompatible"]), "major")

    def test_breaking_bang_with_scope_is_major(self):
        self.assertEqual(release.decide_bump(["feat(api)!: cambio incompatible"]), "major")

    def test_breaking_change_footer_is_major(self):
        commit = "feat: cambio\n\nBREAKING CHANGE: formato incompatible"
        self.assertEqual(release.decide_bump([commit]), "major")

    def test_breaking_change_hyphenated_footer_is_major(self):
        commit = "fix: cambio\n\nBREAKING-CHANGE: formato incompatible"
        self.assertEqual(release.decide_bump([commit]), "major")

    def test_major_has_priority_over_feature(self):
        commits = ["feat: nueva funcion", "fix(core)!: API incompatible"]
        self.assertEqual(release.decide_bump(commits), "major")

    def test_non_feature_commit_is_patch(self):
        self.assertEqual(release.decide_bump(["fix: corregir un error"]), "patch")


class BumpVersionTests(unittest.TestCase):
    def test_bumps_each_semver_component(self):
        self.assertEqual(release.bump_version((1, 2, 3), "major"), (2, 0, 0))
        self.assertEqual(release.bump_version((1, 2, 3), "minor"), (1, 3, 0))
        self.assertEqual(release.bump_version((1, 2, 3), "patch"), (1, 2, 4))

    def test_rejects_unknown_bump(self):
        with self.assertRaises(ValueError):
            release.bump_version((1, 2, 3), "unknown")


if __name__ == "__main__":
    unittest.main()
