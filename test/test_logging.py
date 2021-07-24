import os
import sys
from typing import Any


def test_setup_logging(monkeypatch: Any, tmpdir: str, caplog: Any) -> None:
    from pynvim import setup_logging

    major_version = sys.version_info[0]

    setup_logging('name1')
    assert caplog.messages == []

    def get_expected_logfile(prefix: str, name: str) -> str:
        return '{}_py{}_{}'.format(prefix, major_version, name)

    prefix = tmpdir.join('testlog1')
    monkeypatch.setenv('NVIM_PYTHON_LOG_FILE', str(prefix))
    setup_logging('name2')
    assert caplog.messages == []
    logfile = get_expected_logfile(prefix, 'name2')
    assert os.path.exists(logfile)
    assert open(logfile, 'r').read() == ''

    monkeypatch.setenv('NVIM_PYTHON_LOG_LEVEL', 'invalid')
    setup_logging('name3')
    assert caplog.record_tuples == [
        ('pynvim', 30, "Invalid NVIM_PYTHON_LOG_LEVEL: 'invalid', using INFO."),
    ]
    logfile = get_expected_logfile(prefix, 'name2')
    assert os.path.exists(logfile)
    with open(logfile, 'r') as f:
        lines = f.readlines()
        assert len(lines) == 1
        assert lines[0].endswith(
            "- Invalid NVIM_PYTHON_LOG_LEVEL: 'invalid', using INFO.\n"
        )
