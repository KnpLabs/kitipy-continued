import click
import kitipy
import pytest
from kitipy import *
from unittest import mock


def test_local_only():
    click_ctx = mock.Mock(spec=click.Context)
    kctx = mock.Mock(spec=kitipy.Context)

    click_ctx.find_object.return_value = kctx
    kctx.is_remote = mock.PropertyMock()

    type(kctx).is_local = mock.PropertyMock(return_value=True)

    assert kitipy.filters.local_only(click_ctx) == True


def test_local_only_when_no_kitipy_context_available():
    click_ctx = mock.Mock(spec=click.Context)
    kctx = mock.Mock(spec=kitipy.Context)

    click_ctx.find_object.return_value = None

    assert kitipy.filters.local_only(click_ctx) == False


def test_remote_only():
    click_ctx = mock.Mock(spec=click.Context)
    kctx = mock.Mock(spec=kitipy.Context)
    click_ctx.find_object.return_value = kctx

    type(kctx).is_remote = mock.PropertyMock(return_value=False)

    assert kitipy.filters.remote_only(click_ctx) == False


def test_remote_only_when_no_kitipy_context_available():
    click_ctx = mock.Mock(spec=click.Context)
    kctx = mock.Mock(spec=kitipy.Context)

    click_ctx.find_object.return_value = None

    assert kitipy.filters.remote_only(click_ctx) == False
