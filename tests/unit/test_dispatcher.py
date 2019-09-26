import pytest
import kitipy
from unittest import mock


def test_dispatcher_calls_multiple_listener():
    listener1 = mock.Mock(return_value=True)
    listener2 = mock.Mock(return_value=True)

    dispatcher = kitipy.Dispatcher()
    dispatcher.on('test', listener1)
    dispatcher.on('test', listener2)

    dispatcher.emit('test', some='args')

    listener1.assert_called_once_with(some='args')
    listener2.assert_called_once_with(some='args')


def test_dispatcher_calls_early_stop():
    listener1 = mock.Mock(return_value=False)
    listener2 = mock.Mock(return_value=True)

    dispatcher = kitipy.Dispatcher()
    dispatcher.on('test', listener1)
    dispatcher.on('test', listener2)

    dispatcher.emit('test', some='args')

    listener1.assert_called_once_with(some='args')
    listener2.assert_not_called()
