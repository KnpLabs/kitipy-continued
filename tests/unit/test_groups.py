import click
import kitipy
import pytest
from unittest import mock


@pytest.fixture
def executor():
    return mock.MagicMock(spec=kitipy.Executor)


@pytest.fixture
def kctx(executor):
    kctx = mock.MagicMock(spec=kitipy.Context)
    kctx.executor = executor
    return kctx


@pytest.fixture
def click_ctx(kctx):
    ctx = mock.MagicMock(spec=click.Context)
    ctx.params = {}
    ctx.args = []
    ctx.protected_args = []
    ctx.find_object.return_value = kctx
    return ctx


def test_task_is_disabled_when_one_of_its_filter_is_negative(click_ctx):
    filter = mock.Mock(return_value=False)
    task = kitipy.Task(name='foobar', filters=[filter])

    assert task.is_enabled(click_ctx) == False
    filter.assert_called()


def test_task_is_disabled_when_it_is_hidden(click_ctx):
    filter = mock.Mock(return_value=True)
    task = kitipy.Task(name='foobar', filters=[filter])
    task.hidden = True

    assert task.is_enabled(click_ctx) == False
    filter.assert_called()


def test_task_is_enabled(click_ctx):
    filter = mock.Mock(return_value=True)
    task = kitipy.Task(name='foobar', filters=[filter])

    assert task.is_enabled(click_ctx) == True
    filter.assert_called()


def test_invoke_disabled_task_raises_an_exception(click_ctx):
    task = kitipy.Task(name='foobar')
    task.hidden = True

    with pytest.raises(kitipy.TaskError):
        task.invoke(click_ctx)


def test_task_invoke_updates_the_executor_basedir_using_the_task_cwd(
        click_ctx, kctx):
    task = kitipy.Task(name='foobar', cwd='some/base/dir')
    task.invoke(click_ctx)

    kctx.cd.assert_called_with('some/base/dir')


def test_task_invoke_calls_the_task_callback(kctx):
    task = kitipy.Task(name='foobar')
    task.callback = mock.Mock()

    click_ctx = click.Context(task, obj=kctx)

    task.invoke(click_ctx)

    task.callback.assert_called()


def test_group_is_disabled_when_one_of_its_filter_is_negative(click_ctx):
    filter = mock.Mock(return_value=False)
    group = kitipy.Group(name='foobar', filters=[filter])

    assert group.is_enabled(click_ctx) == False
    filter.assert_called()


def test_group_is_disabled_when_it_is_hidden(click_ctx):
    filter = mock.Mock(return_value=True)
    group = kitipy.Group(name='foobar', filters=[filter])
    group.hidden = True

    assert group.is_enabled(click_ctx) == False
    filter.assert_called()


def test_group_is_enabled(click_ctx):
    filter = mock.Mock(return_value=True)
    group = kitipy.Group(name='foobar', filters=[filter])

    assert group.is_enabled(click_ctx) == True
    filter.assert_called()


def test_invoke_disabled_group_raises_an_exception(click_ctx):
    group = kitipy.Group(name='foobar')
    group.hidden = True

    with pytest.raises(kitipy.TaskError):
        group.invoke(click_ctx)


def test_group_invoke_updates_the_executor_basedir_using_the_group_cwd(kctx):
    group = kitipy.Group(name='foobar',
                         cwd='some/base/dir',
                         callback=mock.Mock(),
                         invoke_without_command=True)

    click_ctx = click.Context(group, obj=kctx)
    group.invoke(click_ctx)

    kctx.cd.assert_called_with('some/base/dir')
    group.callback.assert_called()


def test_group_merging_adds_source_commands_and_transparent_groups():
    src_foo = kitipy.Task(name='foo')
    src_bar = click.Command(name='bar')
    src_baz = kitipy.Group(name='baz')
    src_acme = kitipy.Group(name='acme', tasks=[src_baz])
    src = kitipy.Group(commands={'bar': src_bar},
                       tasks=[src_foo],
                       transparents=[src_acme])

    dest_first = kitipy.Task(name='first')
    dest = kitipy.Group(tasks=[dest_first])
    dest.merge(src)

    expected = [
        'bar',
        'baz',
        'first',
        'foo',
    ]
    assert dest.list_commands(click_ctx) == expected
    assert dest.transparent_groups == [src_acme]


def test_group_get_command_looks_for_the_given_command_in_transparent_groups():
    foo = kitipy.Task(name='foo')
    acme = kitipy.Group(name='acme', tasks=[foo])
    root = kitipy.Group(name='root', transparents=[acme])

    click_ctx = click.Context(root)
    assert root.get_command(click_ctx, 'foo') == foo


def test_group_get_command_cannot_retrieve_transparent_groups_themselves():
    acme = kitipy.Group(name='acme')
    root = kitipy.Group(transparents=[acme])

    click_ctx = click.Context(root)
    assert root.get_command(click_ctx, 'acme') is None


def test_group_get_command_still_retrieves_usual_commands():
    foo = kitipy.Task(name='foo')
    bar = click.Command(name='bar')
    root = kitipy.Group(commands={'bar': bar}, tasks=[foo])

    click_ctx = click.Context(root)
    assert root.get_command(click_ctx, 'foo') is not None
    assert root.get_command(click_ctx, 'bar') is not None


def test_group_get_command_fails_to_find_disabled_tasks():
    foo = kitipy.Task(name='foo', filters=[lambda _: False])
    root = kitipy.Group(tasks=[foo])

    click_ctx = click.Context(root)
    assert root.get_command(click_ctx, 'foo') is None


def test_group_get_command_fails_to_find_disabled_tasks_from_transparent_group(
):
    foo = kitipy.Task(name='foo', filters=[lambda _: False])
    acme = kitipy.Group(tasks=[foo])
    root = kitipy.Group(name='root', transparents=[acme])

    click_ctx = click.Context(root)
    assert root.get_command(click_ctx, 'foo') is None


def test_group_get_command_raises_an_exception_if_the_name_of_a_command_and_of_a_task_from_a_transparent_group_collides(
):
    foo = kitipy.Task(name='foo')
    acme = kitipy.Group(name='acme', tasks=[foo])
    root = kitipy.Group(tasks=[foo], transparents=[acme])

    click_ctx = click.Context(root)
    with pytest.raises(RuntimeError):
        root.get_command(click_ctx, 'foo')


def test_group_get_command_raises_an_exception_if_the_name_of_tasks_from_two_transparent_groups_collides(
):
    foo = kitipy.Task(name='foo')
    acme = kitipy.Group(name='acme', tasks=[foo])
    plop = kitipy.Group(name='plop', tasks=[foo])

    root = kitipy.Group(transparents=[acme, plop])

    click_ctx = click.Context(root)
    with pytest.raises(RuntimeError):
        root.get_command(click_ctx, 'foo')


def test_group_list_commands_looks_for_commands_in_transparent_groups():
    foo = kitipy.Task(name='foo')
    bar = kitipy.Task(name='bar')
    foobar = kitipy.Task(name='foobar', filters=[lambda _: False])
    acme = kitipy.Group(name='acme', tasks=[foo])
    plop = kitipy.Group(name='plop', tasks=[bar, foobar])

    ktp = kitipy.Task(name='ktp')
    baz = click.Command(name='baz')
    knp = kitipy.Task(name='knp', filters=[lambda _: False])

    root = kitipy.Group(commands={'baz': baz},
                        tasks=[ktp, knp],
                        transparents=[acme, plop])

    click_ctx = click.Context(root)
    assert root.list_commands(click_ctx) == ['bar', 'baz', 'foo', 'ktp']


def test_group_list_command_raises_an_exception_if_the_name_of_a_command_and_of_a_task_from_a_transparent_group_collides(
):
    foo = kitipy.Task(name='foo')
    acme = kitipy.Group(name='acme', tasks=[foo])
    root = kitipy.Group(tasks=[foo], transparents=[acme])

    click_ctx = click.Context(root)
    with pytest.raises(RuntimeError):
        root.list_commands(click_ctx)


def test_group_list_commands_raises_an_exception_if_the_name_of_tasks_from_two_transparent_groups_collides(
):
    foo = kitipy.Task(name='foo')
    acme = kitipy.Group(name='acme', tasks=[foo])
    plop = kitipy.Group(name='plop', tasks=[foo])

    root = kitipy.Group(transparents=[acme, plop])

    click_ctx = click.Context(root)
    with pytest.raises(RuntimeError):
        root.list_commands(click_ctx)


def test_task_decorator_from_group_object_creates_a_new_task_object():
    root = kitipy.Group(name='root')
    task = root.task(name='foo', cwd='some/base/dir')(lambda _: ())

    assert root.tasks == [task]
    assert isinstance(task, kitipy.Task)
    assert task.name == 'foo'
    assert task.cwd == 'some/base/dir'


def test_group_decorator_from_group_object_creates_a_child_group():
    root = kitipy.Group(name='root')
    acme = root.group(name='acme', cwd='some/basedir')(lambda _: ())

    assert root.tasks == [acme]
    assert isinstance(acme, kitipy.Group)
    assert acme.name == 'acme'
    assert acme.cwd == 'some/basedir'


def test_stage_group_decorator_from_group_object_creates_a_child_transparent_group(
):
    root = kitipy.Group(name='root')
    acme = root.stage_group()(lambda: ())

    assert isinstance(acme, kitipy.StageGroup)
    assert root.transparent_groups == [acme]


# def test_stage_group_does_not_accept_cwd():
#     with pytest.raises(RuntimeError):
#         kitipy.StageGroup(name='yolo', cwd='yolo')


def test_stack_group_decorator_from_group_object_creates_a_child_transparent_group(
):
    root = kitipy.Group(name='root')
    acme = root.stack_group()(lambda: ())

    assert isinstance(acme, kitipy.StackGroup)
    assert root.transparent_groups == [acme]


# def test_stack_group_does_not_accept_cwd():
#     with pytest.raises(RuntimeError):
#         kitipy.StackGroup(name='yolo', cwd='yolo')


def test_stage_group_automatically_adds_a_stage_if_the_one_accessed_does_not_existt(
):
    stages = kitipy.StageGroup(name='stages')

    assert isinstance(stages.dev, kitipy.Group)
    assert isinstance(stages.prod, kitipy.Group)


def test_overriding_groups_parmeters_in_stages_group():
    stages = kitipy.StageGroup(name='stages')
    assert len(stages.dev.filters) == 0

    stages.stage('dev', filters=[lambda _: True])(lambda _: ())
    assert len(stages.dev.filters) == 1


def test_stages_group_list_commands_returns_the_intersection_of_configured_stages_and_stages_in_the_group(
        click_ctx, kctx):
    stages = kitipy.StageGroup(name='stages')
    stages.stage('dev')
    stages.stage('prod')
    stages.stage('other')

    config = {'stages': {'dev': {}, 'prod': {}}}
    kctx.config = mock.PropertyMock(wraps=config)

    assert list(stages.list_commands(click_ctx)) == ['dev', 'prod']


def test_stages_group_get_command_returns_nothing_if_the_requested_stage_is_not_in_the_config(
        click_ctx, kctx):
    stages = kitipy.StageGroup(name='stages')
    stages.stage('dev')
    stages.stage('prod')
    stages.stage('other')

    config = {'stages': {'dev': {}, 'prod': {}}}
    kctx.config = mock.PropertyMock(wraps=config)

    assert stages.get_command(click_ctx, 'other') is None


def test_adding_a_task_to_a_whole_stages_group_adds_them_to_all_of_the_subgroups(
        click_ctx, kctx):
    stages = kitipy.StageGroup(name='stages')
    stages.all.task(name='foo')(lambda _: ())

    config = {'stages': {'dev': {}, 'prod': {}}}
    kctx.config = mock.PropertyMock(wraps=config)

    dev_group = stages.get_command(click_ctx, 'dev')
    prod_group = stages.get_command(click_ctx, 'prod')

    assert dev_group.list_commands(click_ctx) == ['foo']
    assert prod_group.list_commands(click_ctx) == ['foo']


def test_adding_a_stacks_group_to_a_whole_stages_group_adds_it_to_all_of_the_stages_subgroups(
        click_ctx, kctx):
    stages = kitipy.StageGroup(name='stages')
    stacks = stages.stack_group(name='stacks')(lambda: ())

    assert isinstance(stacks, kitipy.StackGroup)
    assert stages.all.transparent_groups == [stacks]

    config = {
        'stages': {
            'dev': {},
            'prod': {}
        },
        'stacks': {
            'api': {},
            'front': {}
        }
    }
    kctx.config = mock.PropertyMock(wraps=config)

    dev_group = stages.get_command(click_ctx, 'dev')
    prod_group = stages.get_command(click_ctx, 'prod')

    assert dev_group.list_commands(click_ctx) == ['api', 'front']
    assert prod_group.list_commands(click_ctx) == ['api', 'front']


def test_adding_a_stages_group_to_another_stages_group_raises_an_exception(
        click_ctx, kctx):
    stages = kitipy.StageGroup(name='stages')

    with pytest.raises(RuntimeError):
        stages.stage_group(name='another')


def test_invoking_a_stages_group_is_not_supported(click_ctx):
    stages = kitipy.StageGroup(name='stages')

    with pytest.raises(RuntimeError):
        stages.invoke(click_ctx)


def test_stacks_group_automatically_adds_a_stack_if_the_one_accessed_does_not_existt(
):
    stacks = kitipy.StackGroup(name='stacks')

    assert isinstance(stacks.api, kitipy.Group)
    assert isinstance(stacks.front, kitipy.Group)


def test_overriding_groups_parmeters_in_stacks_group():
    stacks = kitipy.StackGroup(name='stacks')
    assert len(stacks.api.filters) == 0

    stacks.stack('api', filters=[lambda _: True])(lambda _: ())
    assert len(stacks.api.filters) == 1


def test_stacks_group_list_commands_returns_the_intersection_of_configured_stacks_and_stacks_in_the_group(
        click_ctx, kctx):
    stacks = kitipy.StackGroup(name='stacks')
    stacks.stack('api')
    stacks.stack('front')
    stacks.stack('back')

    config = {'stacks': {'api': {}, 'front': {}}}
    kctx.config = mock.PropertyMock(wraps=config)

    assert list(stacks.list_commands(click_ctx)) == ['api', 'front']


def test_stacks_group_get_command_returns_nothing_if_the_requested_stack_is_not_in_the_config(
        click_ctx, kctx):
    stacks = kitipy.StackGroup(name='stacks')
    stacks.stack('api')
    stacks.stack('front')
    stacks.stack('back')

    config = {'stacks': {'api': {}, 'front': {}}}
    kctx.config = mock.PropertyMock(wraps=config)

    assert stacks.get_command(click_ctx, 'other') is None


def test_adding_a_task_to_a_whole_stacks_group_adds_them_to_all_of_the_subgroups(
        click_ctx, kctx):
    stacks = kitipy.StackGroup(name='stacks')
    stacks.all.task(name='foo')(lambda _: ())

    config = {'stacks': {'api': {}, 'front': {}}}
    kctx.config = mock.PropertyMock(wraps=config)

    api_group = stacks.get_command(click_ctx, 'api')
    front_group = stacks.get_command(click_ctx, 'front')

    assert api_group.list_commands(click_ctx) == ['foo']
    assert front_group.list_commands(click_ctx) == ['foo']


def test_adding_a_stages_group_to_a_whole_stacks_group_adds_it_to_all_of_the_stack_subgroups(
        click_ctx, kctx):
    stacks = kitipy.StackGroup(name='stacks')
    stages = stacks.stage_group(name='stages')(lambda: ())

    assert isinstance(stages, kitipy.StageGroup)
    assert stacks.all.transparent_groups == [stages]

    config = {
        'stages': {
            'dev': {},
            'prod': {}
        },
        'stacks': {
            'api': {},
            'front': {}
        }
    }
    kctx.config = mock.PropertyMock(wraps=config)

    api_group = stacks.get_command(click_ctx, 'api')
    front_group = stacks.get_command(click_ctx, 'front')

    assert api_group.list_commands(click_ctx) == ['dev', 'prod']
    assert front_group.list_commands(click_ctx) == ['dev', 'prod']


def test_adding_a_stack_group_to_another_stack_group_raises_an_exception(
        click_ctx, kctx):
    stacks = kitipy.StackGroup(name='stacks')

    with pytest.raises(RuntimeError):
        stacks.stack_group(name='another')


def test_invoking_a_stacks_group_is_not_supported(click_ctx):
    stacks = kitipy.StackGroup(name='stacks')

    with pytest.raises(RuntimeError):
        stacks.invoke(click_ctx)
