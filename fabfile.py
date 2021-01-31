"""
Available commands:
 - fab release [--bump=minor] : insert new version to project settings and update Changelog file from git log
 - fab finish : commit updated ChangeLog file, update version line in project settings and commit changes with tag
 - fab check : checks code using isort, flake8, mypy, pylint, black with sensible defaults

Usage example: project release
 1. fab release --bump=major
 2. <prettify updated Changelog by hand>
 3. fab finish

Usage example to check code:
 1. fab check --path=t2f/api/v1/registration.py  # checks file `registretion.py`
 2. <fixing errors>
 3. fab check  # checks the entire project
"""
import os
import sys
from copy import copy
from dataclasses import dataclass, fields

from dateutil.utils import today
from invoke import task

file_dir_path = os.path.dirname(__file__)

CHANGELOG_FILE = "CHANGELOG.md"
VERSION_TITLE_TMPL = "## version {version} ({day})"
CHANGE_LINE_TMPL = "  - {line}"

# validate changelog file path on import
CHANGELOG_ABSPATH = os.path.abspath(os.path.join(file_dir_path, CHANGELOG_FILE))
if not os.path.isfile(CHANGELOG_ABSPATH):
    sys.stderr.write(f'Can\'t find "{CHANGELOG_FILE}" file at {CHANGELOG_ABSPATH}\n')
    sys.exit(1)

# validate that settings could be found
SETTINGS_PATH = os.path.abspath(os.path.join(file_dir_path, "t2f", "core", "config.py"))
if not os.path.isfile(SETTINGS_PATH):
    sys.stderr.write(f"Can't find settings file with VERSION constant at {SETTINGS_PATH}\n")
    sys.exit(1)


@dataclass
class VersionStructure:
    major: int
    minor: int
    patch: int

    @classmethod
    def from_str(cls, line) -> "VersionStructure":
        """
        return object from {line}, e.g. "0.8.16"
        """
        major, minor, patch = [int(item) for item in line.split(".")]
        return cls(major=major, minor=minor, patch=patch)

    @classmethod
    def from_settings(cls) -> "VersionStructure":
        """
        return last version from "settings.py" file
        :rtype: unicode
        """

        with open(SETTINGS_PATH) as f:
            for line in f.readlines():
                if line.startswith("VERSION"):
                    return cls.from_str(line.split("=", 1)[-1].strip("\n '\""))

    @classmethod
    def bump_version(cls, version, part="patch"):
        """
        increment {part} of version
        """
        resulting_version = copy(version)
        version_parts = [f.name for f in fields(resulting_version)]
        assert part in version_parts, f"{part} is not a version part"
        # setattr(self, part, (getattr(self, part, 0) + 1))
        old_version = getattr(resulting_version, part, 0)

        part_to_increment = version_parts.index(part)
        for index, value in enumerate(version_parts):
            if index == part_to_increment:
                setattr(resulting_version, value, old_version + 1)
            elif index > part_to_increment:
                setattr(resulting_version, value, 0)

        return resulting_version

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def to_release_brach_name(self) -> str:
        """
        Convert version for release branch name. Patch part is not used to allow release branch contain hotfixes.
        """
        return f"release/{self.major}.{self.minor}"


def _set_settings_version(c, settings_path, version_line):
    """
    set `VERSION` constant in project settings
    """
    version_const = "VERSION"

    print(f"Adjusting {version_const} in {settings_path} to {version_line}...")
    c.run(f'sed -i .orig \'s/^{version_const} =.*$/{version_const} = "{version_line}"/\' "{settings_path}"')


@task
def release(c, bump="patch"):
    """
    fab release will insert new version to project settings and update Changelog file from git log
    """
    assert bump in [f.name for f in fields(VersionStructure)], f'"{bump}" is not a version part'

    old_version = VersionStructure.from_settings()
    new_version = VersionStructure.bump_version(old_version, part=bump)

    # collecting changelog
    print(f'Collecting changelog from the last version tag "{old_version}"...')

    result = c.run(f'git log "{old_version}"..HEAD --pretty=format:"%s"', hide="out")

    commit_messages = filter(bool, result.stdout.splitlines())
    if not commit_messages:
        sys.stderr.write("Error: no new commits from last version, sorry\n")
        sys.exit(1)

    # updating changelog
    with open(CHANGELOG_ABSPATH, "r+", encoding="utf-8") as changelog:
        old_changelog = changelog.read().strip()

        changelog.seek(0)
        print("Inserting this to changelog file:\n-----\n")
        new_version_line = (
            VERSION_TITLE_TMPL.format(version=new_version, day=today().strftime("%Y-%m-%d")) + "\n"
        )
        changelog.write(new_version_line)

        print(new_version_line)
        for line in sorted(commit_messages):  # sort commit messages for easier edition afterwards
            line: str = line.strip()
            if line.startswith("Merge"):
                continue

            message_line = CHANGE_LINE_TMPL.format(line=line) + "\n"
            print(message_line)
            changelog.write(message_line)

        changelog.write("\n")
        changelog.write(old_changelog)

        print("-----")

    _set_settings_version(c, SETTINGS_PATH, str(new_version))


@task
def finish(c):
    """
    commit updated ChangeLog file, update version line in project settings and commit changes with tag
    """
    files_to_commit = [os.path.relpath(path, start=os.curdir) for path in [CHANGELOG_ABSPATH, SETTINGS_PATH]]
    version: VersionStructure = VersionStructure.from_settings()

    c.run(f"git add %s" % " ".join(files_to_commit))
    c.run(f'git commit -m "version {version}" --no-verify')
    c.run(f"git tag {version}")


@task
def check(c, path=None, lines=110):
    """
    check code using isort, flake8 and mypy
    """
    default_env = {
        "SECRET_KEY": os.environ.get("SECRET_KEY", "fab check key"),
        "PATH": os.environ["PATH"],
        "LANG": "en_US.UTF-8",
    }

    env = os.environ
    env.update(default_env)

    commands = [
        'echo "=> Checking in \\"%s\\":"' % (path or "t2f"),
        # black
        'echo "\n\n=> running `black --version` ...\n"',
        f"black --line-length={lines} %s" % (path or "."),
        'echo "\n=> done!"',
        # mypy
        'echo "\n\n=> running `mypy --version` ...\n"',
        "mypy --config-file ./mypy.ini %s" % (path or "t2f"),
        'echo "\n=> done!"',
        # flake8
        'echo "\n\n=> running flake8 `flake8 --version` ...\n"',
        "flake8 %s" % (path or "t2f"),
        'echo "\n=> done!"',
        # pylint
        'echo "\n\n=>running `pylint --version` ...\n"',
        "python pylint-checker.py %s --fail-under=9.8" % (path or "t2f"),
        'echo "\n=> done!"',
    ]

    [c.run(cmd, env=env, warn=True) for cmd in commands]


@task(name="load-testdb")
def load_testdb(c, dbname="test_template", fpath="tests/test_db.sql"):
    """
    Load db for tests from {fpath} file to {dbname} to allow for easy changing of data
    """
    default_env = {
        "PATH": os.environ["PATH"],
        "PYTHONPATH": os.path.abspath(os.path.dirname(__file__)),
        "LANG": "en_US.UTF-8",
        "POSTGRES_DB": dbname,
        "POSTGRES_HOST": "localhost",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PORT": "5432",
    }

    env = os.environ
    env.update(default_env)

    psql_command = (
        f'psql -h {default_env["POSTGRES_HOST"]} '
        f'-p {default_env["POSTGRES_PORT"]} '
        f'-U {default_env["POSTGRES_USER"]}'
    )

    c.run(f'{psql_command} postgres -c "drop database if exists {dbname}";', env=env)
    c.run(f'{psql_command} postgres -c "create database {dbname}";', env=env)
    c.run(f"{psql_command} {dbname} < {fpath}", env=env)
    # update test db to the latest migrations
    c.run(f"alembic -c ./alembic.ini upgrade head", env=env)


@task(name="dump-testdb")
def dump_testdb(c, dbname="test_template", fpath="tests/test_db.sql"):
    """
    Dump {dbname} to test db file {fpath}
    """
    default_env = {
        "PATH": os.environ["PATH"],
        "LANG": "en_US.UTF-8",
    }

    env = os.environ
    env.update(default_env)

    c.run(f"pg_dump -h localhost -p 5432 -U postgres {dbname} > {fpath}", env=env)
