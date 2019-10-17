#!/usr/bin/env python3
import click
import kitipy
import kitipy.docker
import kitipy.docker.tasks
import os
import sys
from typing import Optional, List

config = {
    'stacks': {
        'kitipy': {
            'file': 'tests/docker-compose.yml',
        },
    },
}


def pytest(kctx: kitipy.Context, cmd: str, **args):
    env = os.environ.copy()
    env['PYTHONPATH'] = os.getcwd()
    args.setdefault('env', env)

    kctx.local('pytest ' + cmd, **args)


@kitipy.root(config_file=None, config=config)
def root():
    pass


@root.task()
@click.option('--diff/--no-diff', 'show_diff', default=True)
@click.option('--force', is_flag=True, default=None)
def format(kctx: kitipy.Context, show_diff, force):
    """Run yapf to detect style divergences and fix them."""
    confirm_message = 'Do you want to reformat your code using yapf?'
    apply = show_diff is False

    if show_diff:
        diff = kctx.local('yapf --diff -r kitipy/ tests/ tasks*.py',
                          check=False)
        confirm_message = 'Do you want to apply this diff?'
        apply = diff.returncode != 0

    if force is None and apply:
        force = click.confirm(confirm_message, default=True)
    if force and apply:
        kctx.local('yapf -vv -p -i -r kitipy/ tests/ tasks*.py')


@root.task()
def lint(kctx: kitipy.Context):
    """Run mypy, a static type checker, to detect type errors."""
    kctx.local('mypy -p kitipy')
    # @TODO: find a way to fix types errors in tasks files
    # kctx.local('mypy tasks*.py')


@root.group()
def test():
    pass


@test.task(name='all')
def test_all(kctx: kitipy.Context):
    """Execute all the tests suites."""
    kctx.invoke(test_unit)
    kctx.invoke(test_tasks)


@test.task(name='unit')
def test_unit(kctx: kitipy.Context):
    # Be sure the SSH container used for tests purpose is up and running.
    # @TODO: add a common way to kitipy to wait for a port to be open
    kctx.invoke(kitipy.docker.tasks.up)

    expected_services = len(kctx.stack.config['services'])
    # @TODO: this won't work as is with Swarm, find how to generalize that sort of tests
    tester = lambda kctx: expected_services == kctx.stack.count_services(
        filter=('status=running'))
    kitipy.wait_for(tester,
                    interval=1,
                    max_checks=5,
                    label="Waiting for services start up...")

    # Host key might change if docker-compose down is used between two test run,
    # thus we start by removing any existing host key.
    kctx.local("ssh-keygen -R '[127.0.0.1]:2022' 1>/dev/null 2>&1")
    kctx.local("ssh-keygen -R '[127.0.0.1]:2023' 1>/dev/null 2>&1")
    kctx.local("ssh-keygen -R testhost 1>/dev/null 2>&1")

    # Ensure the private key has the right chmod or the task might fail.
    os.chmod("tests/.ssh/id_rsa", 0o0600)

    # Ensure first that we're actually able to connect to SSH hosts, or
    # tests will fail anyway.
    kctx.local('ssh -F tests/.ssh/config testhost /bin/true 1>/dev/null 2>&1')
    kctx.local('ssh -F tests/.ssh/config jumphost /bin/true 1>/dev/null 2>&1')
    kctx.local(
        'ssh -F tests/.ssh/config testhost-via-jumphost /bin/true 1>/dev/null 2>&1'
    )

    pytest(kctx, 'tests/unit/ -vv')


@test.task(name='tasks')
@click.argument('suites', nargs=-1, type=str)
def test_tasks(kctx: kitipy.Context, suites: List[str]):
    if len(suites) == 0:
        pytest(kctx, 'tests/tasks/ -vv')
        return

    for suite in suites:
        pytest(kctx, 'tests/tasks/test_%s.py -vv' % (suite))


@test.task(name='generate-git-tgz')
@click.option('--keep-tmp-dir', 'keep', type=bool, default=False, is_flag=True)
def test_generate_git_tgz(kctx: kitipy.Context, keep: bool):
    """(Re) Generate tests/git-archive.tgz.
    
    This command has been implemented and used to generate the original
    tests/git-archive.tgz file, which is used to test git-related helper
    functions.
    """
    tempdir = kctx.executor.mkdtemp()
    commands = ['cd ' + tempdir, 'git init']
    commits = (
        ('foo', 'v0.1'),
        ('bar', 'v0.2'),
        ('baz', 'v0.3'),
        ('pi', 'v0.4'),
        ('yolo', 'v0.5'),
    )

    for commit, tag in commits:
        commands.append('touch ' + commit)
        commands.append('git add ' + commit)
        commands.append('git commit -m "%s"' % (commit))
        commands.append('git tag %s HEAD' % (tag))

    basedir = os.path.dirname(os.path.abspath(__file__))
    tgz_path = os.path.join(basedir, 'tests', 'tasks', 'testdata',
                            'git-repo.tgz')
    commands.append('tar zcf %s .' % (tgz_path))

    try:
        kctx.run(' && '.join(commands))
    finally:
        if not keep:
            kctx.run('rm -rf %s' % (tempdir))


root.add_command(kitipy.docker.tasks.compose)

if __name__ == "__main__":
    root()
