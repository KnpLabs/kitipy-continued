import kitipy
import os
import pytest
from unittest.mock import Mock
from kitipy import *


def append_cmd_flags_testdata():
    return [
        ("foo", {
            "d": True
        }, "foo -d"),
        ("foo", {
            "f": "config.yaml"
        }, "foo -f config.yaml"),
        ("foo", {
            "some": "flag"
        }, "foo --some=flag"),
        ("foo", {
            "filter": ("a", "b")
        }, "foo --filter=a --filter=b"),
        ("foo", {
            "some-bool": True
        }, "foo --some-bool"),
        ("foo", {
            "some-float": 3.141592
        }, "foo --some-float=3.141592"),
    ]


@pytest.mark.parametrize("cmd, flags, expected", append_cmd_flags_testdata())
def test_append_cmd_flags(cmd, flags, expected):
    returned = append_cmd_flags(cmd, **flags)
    assert returned == expected


def test_set_up_file_transfer_listeners():
    dispatcher = Mock(spec=kitipy.dispatcher.Dispatcher)

    set_up_file_transfer_listeners(dispatcher)

    assert dispatcher.on.call_count == 3


def normalize_config_testdata():
    return [
        (
            {},
            {
                'stages': {
                    'default': {
                        'name': 'default',
                        'type': 'local',
                    }
                },
                'stacks': {},
            },
        ),
        (
            {
                'stack': {
                    'name': 'foo',
                    'file': 'docker-compose.yml'
                }
            },
            {
                'stacks': {
                    'foo': {
                        'name': 'foo',
                        'file': 'docker-compose.yml'
                    }
                },
                'stages': {
                    'default': {
                        'name': 'default',
                        'type': 'local',
                    },
                },
            },
        ),
        (
            {
                'stage': {
                    'name': 'dev',
                    'type': 'local',
                }
            },
            {
                'stages': {
                    'dev': {
                        'name': 'dev',
                        'type': 'local'
                    }
                },
                'stacks': {},
            },
        ),
        ({
            'stacks': {
                'foo': {
                    'file': 'docker-compose.yml',
                },
            },
            'stages': {
                'dev': {
                    'type': 'local',
                },
            },
        }, {
            'stacks': {
                'foo': {
                    'name': 'foo',
                    'file': 'docker-compose.yml',
                },
            },
            'stages': {
                'dev': {
                    'name': 'dev',
                    'type': 'local',
                }
            }
        }),
    ]


@pytest.mark.parametrize("config, expected", normalize_config_testdata())
def test_normalize_config(config, expected):
    normalized = normalize_config(config)

    assert config == expected


def test_load_config_file():
    filepath = os.path.join(os.path.dirname(__file__), "testdata/config.yml")

    config = load_config_file(filepath)
    expected = {
        'path': filepath,
        'stages': {
            'dev': {
                'type': 'local',
            }
        }
    }

    assert config == expected
