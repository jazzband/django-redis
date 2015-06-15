# -*- coding: utf-8 -*-

import os, sys
sys.path.insert(0, "..")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "test_sqlite_msgpack")

if __name__ == "__main__":
    from django.core.management import execute_from_command_line
    args = sys.argv
    args.insert(1, "test")
    if len(args) == 2:
        args.insert(2, "redis_backend_testapp")
        args.insert(3, "hashring_test")

    execute_from_command_line(args)
