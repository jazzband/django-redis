class CacheKey(str):
    """
    A stub string class that we can use to check if a key was created already.
    """
    def original_key(self):
        return self.rsplit(":", 1)[1]


def default_reverse_key(key):
    return key.split(':', 2)[2]
