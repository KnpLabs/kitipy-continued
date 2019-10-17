import click
import subprocess
from typing import Any, Dict, List, Optional
from .dispatcher import Dispatcher
from .executor import Executor, _create_executor


class Context(object):
    """Kitipy context is the global object carrying the kitipy Executor used to
    ubiquitously run commands on local and remote targets, as well as the stack
    and stage objects loaded by task groups and the dispatcher used to update
    the CLI based on executor events.

    It's acting as a global Facade, such that you generally don't need to
    interact with other kitipy or click objects.

    As both kitipy and click exposes their own Context object, you might wonder
    what's the fundamental difference between them, here it is:

      * As said above, kitipy Context carry everything about how and where to
        execute shell commands, on either local or remote targets. As such, it
        has a central place in kitipy and is what you interact with within 
        kitipy tasks.
      * In the other hand, the click Context is here to carry details about CLI
        commands and options, and to actually parse and navigate the command
        tree made of kitipy tasks or regular click commands. As kitipy is a 
        super-set of click features, click.Context actually embeds the
        kitipy.Context object.

    You generally don't need to instantiate it by yourself, as this is
    handled by RootCommand which can be created through the kitipy.root()
    decorator.
    """

    def __init__(self,
                 config: Dict,
                 executor: Executor,
                 dispatcher: Dispatcher,
                 stage: Optional[Dict[Any, Any]] = None,
                 stack=None):
        """
        Args:
            config (Dict):
                Normalized kitipy config (see normalize_config()).
            executor (kitipy.Executor):
                The command executor used to ubiquitously run commands on local
                and remote targets.
            dispatcher (kitipy.Dispatcher):
                The event dispatcher used by the executor to signal events
                about file transfers and any other event that shall produce
                something on the CLI. This is used to decouple SSH matters 
                from the CLI.
            stage (Optional[Dict[Any, Any]]):
                This is the config for the stage in use.
                There might be no stage available when the Context is built. In
                such case, it can be set afterwards. The stage can be loaded
                through kitipy.load_stage(), but this is handled
                automatically by creating a stack-scoped task group through
                kitipy.task() or kctx.task() decorators.
            stack (Optional[kitipy.docker.BaseStack]):
                This is the stack object representing the Compose/Swarm stack
                in use.
                There might be no stack available when the Context is built. In
                such case, it can be set afterwards. The stack can be loaded
                through kitipy.docker.load_stack(), but this is handled
                automatically by creating a stack-scoped task group through
                kitipy.task() or kctx.task() decorators.
        """
        self.config = config
        self.stage = stage
        self.stack = stack
        self.executor = executor
        self.dispatcher = dispatcher

    def with_stage(self, stage_name: str):
        """Change the current Context stage.

        Args:
            stage_name (str): Name of the stage to use.

        Raises:
            KeyError: If the stage couldn't be found in the Context config.
        """
        self.stage = self.config['stages'][stage_name]
        self.executor = _create_executor(self.config, stage_name,
                                         self.dispatcher)

    def with_stack(self, stack_name: str):
        # This has to be imported here to avoid circular dependencies
        from .docker.stack import load_stack

        self.stack = load_stack(self, stack_name)
        stack_cfg = self.config['stacks'][stack_name]
        self.executor.cd(stack_cfg.get('basedir', './'))

    def run(self, cmd: str, **kwargs) -> subprocess.CompletedProcess:
        """This method is the way to ubiquitously run a command on either local
        or remote target, depending on how the executor was set.

        Args:
            cmd (str): The command to run.
            **kwargs: See Executor.run() options for more details.

        Raises:
            paramiko.SSHException:
                When the SSH client fail to run the command. Note that this
                won't be raised when the command could not be found or it
                exits with code > 0 though, but only when something fails at
                the SSH client/server lower level.
        
        Returns:
            subprocess.CompletedProcess
        """
        return self.executor.run(cmd, **kwargs)

    def local(self, cmd: str, **kwargs) -> subprocess.CompletedProcess:
        """Run a command on local host.
        
        This method is particularly useful when you want to run some commands
        on local host whereas the Executor is running in remote mode. For
        instance, you might want to check if a given git tag or some Docker 
        images exists on a remote repository/registry before deploying it, 
        or you might want to fetch the local git author name to log deployment
        events somewhere. Such checks are generally better run locally.

        Args:
            cmd (str): The command to run.
            **kwargs: See Executor.run() options for more details.

        Raises:
            paramiko.SSHException:
                When the SSH client fail to run the command. Note that this
                won't be raised when the command could not be found or it
                exits with code > 0 though, but only when something fails at
                the SSH client/server lower level.
        
        Returns:
            subprocess.CompletedProcess
        """
        return self.executor.local(cmd, **kwargs)

    def cd(self, path: str):
        self.executor.cd(path)

    def path_exists(self, path: str) -> bool:
        return self.executor.path_exists(path)

    def copy(self, src: str, dest: str):
        """Copy a local file to a given path. If the underlying executor has
        been configured to work in remote mode, the given source path will
        be copied over network."""
        self.executor.copy(src, dest)

    def get_stage_names(self):
        """Get the name of all stages in the configuration"""
        return self.config['stages'].keys()

    def get_stack_names(self):
        """Get the name of all stacks in the configuration"""
        return self.config['stacks'].keys()

    @property
    def is_local(self):
        """Check if current kitipy Executor is in local mode"""
        return self.executor.is_local

    @property
    def is_remote(self):
        """Check if current kitipy Executor is in remote mode"""
        return self.executor.is_remote

    @property
    def meta(self):
        """Meta properties from current click.Context"""
        return click.get_current_context().meta

    def invoke(self, cmd: click.Command, *args, **kwargs):
        """Call invoke() method on current click.Context"""
        parent = click.get_current_context()
        ctx = click.Context(cmd, info_name=cmd.name, parent=parent)

        for param in cmd.params:
            if not param.expose_value or param.name in kwargs:
                continue

            default = param.get_default(ctx)
            if param.name in parent.params:
                default = parent.params[param.name]

            kwargs[param.name] = default

        callback = cmd.callback
        with click.core.augment_usage_errors(parent):
            with ctx:  # type: ignore
                return callback(*args, **kwargs)  # type: ignore

    def echo(self, *args, **kwargs):
        """Call echo() method on current click.Context"""
        return click.echo(*args, **kwargs)

    def info(self, message: str):
        """Output a colored info message (black on cyan) on stderr using :func:`click.secho`."""
        return click.secho('INFO: ' + message,
                           bg='cyan',
                           fg='black',
                           bold=True,
                           err=True)

    def warning(self, message: str):
        """Output a colored warning message (black on yellow) on stderr, using :func:`click.secho`."""
        return click.secho('WARNING: ' + message,
                           bg='yellow',
                           fg='black',
                           bold=True,
                           err=True)

    def error(self, message: str):
        """Output a colored error message (white on red) on stderr using :func:`click.secho`."""
        return click.secho('ERROR: ' + message,
                           bg='red',
                           fg='bright_white',
                           bold=True,
                           err=True)

    def fail(self, message):
        """Call fail() method on current click.Context"""
        raise click.ClickException(message)


pass_context = click.make_pass_decorator(Context)


def get_current_context(click_ctx: Optional[click.Context] = None) -> Context:
    """
    Find the current kitipy context or raise an error.

    Args:
        click_ctx (click.Context):
            The click.Context where this function should look for a
            kitipy.Context.

    Raises:
        RuntimeError: When no kitipy context has been found.
    
    Returns:
        Context: The current kitipy context.
    """

    if click_ctx is None:
        click_ctx = click.get_current_context()

    kctx = click_ctx.find_object(Context)
    if kctx is None:
        raise RuntimeError('No kitipy context found.')
    return kctx


def get_current_executor() -> Executor:
    """
    Get the executor from the current kitipy context or raise an error.

    Raises:
        RuntimeError: When no kitipy context has been found.
    
    Returns:
        Executor: The executor of the current kitipy context.
    """

    kctx = get_current_context()
    return kctx.executor
