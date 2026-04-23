import pytest
from pathlib import Path
from unittest.mock import patch
from memex.project_id import get_project_id


def test_github_ssh_remote():
    with patch("memex.project_id._git_remote", return_value="git@github.com:sham/orbit.git"):
        assert get_project_id(Path("/some/path")) == "github-com-sham-orbit"


def test_github_https_remote():
    with patch("memex.project_id._git_remote", return_value="https://github.com/sham/memex.git"):
        assert get_project_id(Path("/some/path")) == "github-com-sham-memex"


def test_no_git_remote_but_has_repo_falls_back_to_dirname():
    with patch("memex.project_id._git_remote", return_value=None):
        with patch("memex.project_id._has_git_repo", return_value=True):
            assert get_project_id(Path("/Users/sham/my-project")) == "my-project"


def test_no_git_repo_returns_none():
    with patch("memex.project_id._git_remote", return_value=None):
        with patch("memex.project_id._has_git_repo", return_value=False):
            assert get_project_id(Path("/Users/sham")) is None


def test_slug_is_lowercase_and_safe():
    with patch("memex.project_id._git_remote", return_value="https://github.com/Sham/My_Project.git"):
        slug = get_project_id(Path("/any"))
        assert slug == slug.lower()
        assert all(c.isalnum() or c == "-" for c in slug)
