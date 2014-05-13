class Vim(object):
    def foreach_rtp(self, cb):
        """
        For compatibility with the legacy python/vim API. The iteration stops
        when an exception is throwed or the callback returns anything other
        than 'None'
        """
        for path in self.list_runtime_paths():
            try:
                if cb(path) != None:
                    break;
            except:
                break

