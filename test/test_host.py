# -*- coding: utf-8 -*-

from pynvim.plugin.host import Host, host_method_spec


def test_host_clientinfo(vim):
    h = Host(vim)
    assert h._request_handlers.keys() == host_method_spec.keys()
    assert 'remote' == vim.api.get_chan_info(vim.channel_id)['client']['type']
    h._load([])
    assert 'host' == vim.api.get_chan_info(vim.channel_id)['client']['type']
