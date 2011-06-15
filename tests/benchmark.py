"""
A quick and dirty benchmarking script.  GitPython is an optional dependency
which you can use to change branches via the command line.

Usage::

    python benchmark.py
    python benchmark.py master
    python benchamrk.py some-branch
"""

import os
import sys
from time import time
from django.core import cache
from hashlib import sha1 as sha

try:
    from git import Repo
except ImportError:
    pass
else:
    if len(sys.argv) > 1:
        repo_path = os.path.dirname(__file__)
        repo = Repo(repo_path)
        repo.branches[sys.argv[1]].checkout()
        print "Testing %s" % repo.active_branch


def h(value):
    return sha(str(value)).hexdigest()

class BenchmarkRegistry(type):
    def __init__(cls, name, bases, attrs):
        if not hasattr(cls, 'benchmarks'):
            cls.benchmarks = []
        else:
            cls.benchmarks.append(cls)


class Benchmark(object):
    __metaclass__ = BenchmarkRegistry

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def timetrial(self):
        self.setUp()
        start = time()
        self.run()
        t = time() - start
        self.tearDown()
        return t

    def run(self):
        pass

    @classmethod
    def run_benchmarks(cls):
        for benchmark in cls.benchmarks:
            benchmark = benchmark()
            print benchmark.__doc__
            print "Time: %s" % (benchmark.timetrial())


class GetAndSetBenchmark(Benchmark):
    "Settings and Getting Mixed"

    def setUp(self):
        self.cache = cache.get_cache('default')
        self.values = {}
        for i in range(30000):
            self.values[h(i)] = i
            self.values[h(h(i))] = h(i)


    def run(self):
        for k, v in self.values.items():
            self.cache.set(k, v)
        for k, v in self.values.items():
            value = self.cache.get(k)


class IncrBenchmark(Benchmark):
    "Incrementing integers"
    def setUp(self):
        self.cache = cache.get_cache('default')
        self.values = {}
        self.ints = []
        self.strings = []
        for i in range(30000):
            self.values[h(i)] = i
            self.values[h(h(i))] = h(i)
            self.ints.append(i)
            self.strings.append(h(i))

    def run(self):
        for i in self.ints:
            self.cache.incr(h(i), 100)


class MsetAndMGet(Benchmark):
    "Getting and setting many mixed values"

    def setUp(self):
        self.cache = cache.get_cache('default')
        self.values = {}
        for i in range(30000):
            self.values[h(i)] = i
            self.values[h(h(i))] = h(i)

    def run(self):
        self.cache.set_many(self.values)
        value = self.cache.get_many(self.values.keys())


if __name__ == "__main__":
    Benchmark.run_benchmarks()