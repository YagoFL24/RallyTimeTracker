import importlib.util
import os
import tempfile
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


class CommitAndChangelogTests(unittest.TestCase):
    def test_get_commits_since_preserves_body_and_splits_entries(self):
        output = (
            "feat: nueva funcion\n\nDetalle\n<<<END>>>\n"
            "fix: correccion\n<<<END>>>"
        )
        with mock.patch.object(release, "run", return_value=output) as run_mock:
            commits = release.get_commits_since("v1.2.0")

        self.assertEqual(
            commits, ["feat: nueva funcion\n\nDetalle", "fix: correccion"]
        )
        run_mock.assert_called_once_with(
            ["git", "log", "v1.2.0..HEAD", "--pretty=%s%n%b<<<END>>>"]
        )

    def test_build_changelog_uses_only_commit_subjects(self):
        section = release.build_changelog_section(
            "v1.3.0",
            ["feat: nueva funcion\n\nDetalle interno", "fix: correccion"],
        )
        self.assertIn("## v1.3.0 - ", section)
        self.assertIn("- feat: nueva funcion", section)
        self.assertIn("- fix: correccion", section)
        self.assertNotIn("Detalle interno", section)

    def test_update_changelog_prepends_section_after_single_header(self):
        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            try:
                Path("CHANGELOG.md").write_text(
                    "# Changelog\n\n## v1.0.0 - 2026-01-01\n\n- inicial\n",
                    encoding="utf-8",
                )
                release.update_changelog(
                    "## v1.1.0 - 2026-02-01\n\n- feat: mejora\n"
                )
                content = Path("CHANGELOG.md").read_text(encoding="utf-8")
            finally:
                os.chdir(original_cwd)

        self.assertEqual(content.count("# Changelog"), 1)
        self.assertLess(content.index("## v1.1.0"), content.index("## v1.0.0"))

    def test_write_outputs_uses_github_actions_format(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "github-output.txt"
            with mock.patch.dict(
                os.environ, {"GITHUB_OUTPUT": str(output_path)}, clear=False
            ):
                release.write_outputs("v1.3.0", "release_notes.md", True)
            content = output_path.read_text(encoding="utf-8")

        self.assertEqual(
            content,
            "version=v1.3.0\n"
            "release_notes=release_notes.md\n"
            "release=true\n",
        )


class ReleaseMainTests(unittest.TestCase):
    def test_main_skips_files_when_there_are_no_new_commits(self):
        with mock.patch.object(release, "get_latest_tag", return_value="v1.2.3"), \
             mock.patch.object(release, "get_commits_since", return_value=[]), \
             mock.patch.object(release, "write_outputs") as outputs_mock:
            release.main()

        outputs_mock.assert_called_once_with("", "", False)

    def test_main_prepares_minor_release_files_and_outputs(self):
        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            try:
                with mock.patch.object(
                    release, "get_latest_tag", return_value="v1.2.3"
                ), mock.patch.object(
                    release,
                    "get_commits_since",
                    return_value=["feat: nueva funcion", "fix: correccion"],
                ), mock.patch.object(
                    release, "update_changelog"
                ) as changelog_mock, mock.patch.object(
                    release, "write_outputs"
                ) as outputs_mock:
                    release.main()
                notes = Path("release_notes.md").read_text(encoding="utf-8")
            finally:
                os.chdir(original_cwd)

        self.assertIn("## v1.3.0", notes)
        self.assertIn("- feat: nueva funcion", notes)
        changelog_mock.assert_called_once_with(notes)
        outputs_mock.assert_called_once_with("v1.3.0", "release_notes.md", True)


if __name__ == "__main__":
    unittest.main()
