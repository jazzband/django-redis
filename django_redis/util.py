class CacheKey(str):
    """
    A stub string class that we can use to check if a key was created already.
    """

    def original_key(self):
        return self.rsplit(":", 1)[1]


def default_reverse_key(key):
    return key.split(':', 2)[2]


# generator to chunk loop an iterator
def chunk_iter(iterator, size, stop):
    while True:
        result = {next(iterator, stop) for i in range(size)}
        if stop in result:
            result.remove(stop)
            yield result
            break
        yield result


def delete_pattern(params, client):
    chunks = chunk_iter(client.scan_iter(**params), 500, None)

    count = 0

    for keys in chunks:
        if keys:
            client.delete(*list(keys))  # bulk delete
            count += len(keys)

    return count
