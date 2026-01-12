import datetime
import os
import re
import subprocess
from typing import List, Tuple


def run(cmd: List[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def get_latest_tag() -> str:
    try:
        return run(["git", "tag", "--list", "v*", "--sort=-v:refname"]).splitlines()[0]
    except Exception:
        return ""


def parse_version(tag: str) -> Tuple[int, int, int]:
    match = re.match(r"v(\\d+)\\.(\\d+)\\.(\\d+)", tag)
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
        if "BREAKING CHANGE" in entry or re.search(r"^\\w+!:", entry, re.MULTILINE):
            return "major"
    for entry in commits:
        if re.search(r"^feat(\\(.+\\))?:", entry, re.MULTILINE):
            return "minor"
    return "patch"


def bump_version(version: Tuple[int, int, int], bump: str) -> Tuple[int, int, int]:
    major, minor, patch = version
    if bump == "major":
        return (major + 1, 0, 0)
    if bump == "minor":
        return (major, minor + 1, 0)
    return (major, minor, patch + 1)


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
