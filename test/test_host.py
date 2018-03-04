# -*- coding: utf-8 -*-

from pynvim.plugin.host import Host, host_method_spec

def test_host_method_spec(vim):
    h = Host(vim)
    assert h._request_handlers.keys() == host_method_spec.keys()
