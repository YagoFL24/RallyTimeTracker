import datetime
import os
import re
import subprocess
from typing import List, Tuple


SEMVER_NUMBER = r"(?:0|[1-9]\d*)"
SEMVER_TAG_RE = re.compile(
    rf"^v({SEMVER_NUMBER})\.({SEMVER_NUMBER})\.({SEMVER_NUMBER})$"
)
CONVENTIONAL_HEADER_RE = re.compile(
    r"^(?P<type>[A-Za-z][A-Za-z0-9_-]*)(?:\([^\r\n)]+\))?(?P<breaking>!)?:"
)
BREAKING_FOOTER_RE = re.compile(r"^BREAKING(?: |-)CHANGE:\s*", re.MULTILINE)


def run(cmd: List[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def get_latest_tag() -> str:
    try:
        tags = run(
            ["git", "tag", "--merged", "HEAD", "--list", "v*", "--sort=-v:refname"]
        ).splitlines()
    except (OSError, subprocess.SubprocessError):
        return ""
    return next((tag for tag in tags if SEMVER_TAG_RE.fullmatch(tag)), "")


def parse_version(tag: str) -> Tuple[int, int, int]:
    match = SEMVER_TAG_RE.fullmatch(tag)
    if not match:
        return (0, 0, 0)
    return tuple(int(x) for x in match.groups())


def get_commits_since(tag: str) -> List[str]:
    if tag:
        output = run(["git", "log", f"{tag}..HEAD", "--pretty=%s%n%b<<<END>>>"])
    else:
        output = run(["git", "log", "--pretty=%s%n%b<<<END>>>"])
    entries = [entry.strip() for entry in output.split("<<<END>>>") if entry.strip()]
    return entries


def decide_bump(commits: List[str]) -> str:
    if not commits:
        return ""

    for entry in commits:
        header = entry.partition("\n")[0].strip()
        match = CONVENTIONAL_HEADER_RE.match(header)
        if BREAKING_FOOTER_RE.search(entry) or (match and match.group("breaking")):
            return "major"

    for entry in commits:
        header = entry.partition("\n")[0].strip()
        match = CONVENTIONAL_HEADER_RE.match(header)
        if match and match.group("type").lower() == "feat":
            return "minor"

    return "patch"


def bump_version(version: Tuple[int, int, int], bump: str) -> Tuple[int, int, int]:
    major, minor, patch = version
    if bump == "major":
        return (major + 1, 0, 0)
    if bump == "minor":
        return (major, minor + 1, 0)
    if bump == "patch":
        return (major, minor, patch + 1)
    raise ValueError(f"Tipo de incremento no valido: {bump}")


def build_changelog_section(version: str, commits: List[str]) -> str:
    date_str = datetime.date.today().isoformat()
    lines = [f"## {version} - {date_str}", ""]
    for entry in commits:
        subject = entry.splitlines()[0].strip()
        if subject:
            lines.append(f"- {subject}")
    lines.append("")
    return "\n".join(lines)


def update_changelog(section: str) -> None:
    path = "CHANGELOG.md"
    header = "# Changelog\n\n"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()
        if content.startswith(header):
            new_content = header + section + content[len(header) :]
        else:
            new_content = header + section + content
    else:
        new_content = header + section

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(new_content)


def write_outputs(version: str, release_notes_path: str, should_release: bool) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as fh:
        fh.write(f"version={version}\n")
        fh.write(f"release_notes={release_notes_path}\n")
        fh.write(f"release={'true' if should_release else 'false'}\n")


def main() -> None:
    latest_tag = get_latest_tag()
    commits = get_commits_since(latest_tag)
    bump = decide_bump(commits)
    if not bump:
        write_outputs("", "", False)
        return

    current_version = parse_version(latest_tag)
    next_version = bump_version(current_version, bump)
    version_str = f"v{next_version[0]}.{next_version[1]}.{next_version[2]}"

    section = build_changelog_section(version_str, commits)
    update_changelog(section)

    notes_path = "release_notes.md"
    with open(notes_path, "w", encoding="utf-8") as fh:
        fh.write(section)

    write_outputs(version_str, notes_path, True)


if __name__ == "__main__":
    main()
