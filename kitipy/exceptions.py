import click
from typing import Optional


class TaskError(click.ClickException):
    def __init__(self,
                 message: str,
                 click_ctx: Optional[click.Context] = None,
                 exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code
        self.click_ctx = click_ctx

    def show(self, file=None):
        color = self.click_ctx.color if self.click_ctx else None
        msg = click.style('Error: %s' % self.format_message(),
                          fg='bright_white',
                          bg='red')
        click.echo(msg, file=file, color=color)
