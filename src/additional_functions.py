from git import Repo  # pip install gitpython


def clone(git_url, repo_dir):
    Repo.clone_from(git_url, repo_dir)