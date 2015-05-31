# -*- coding: utf-8 -*-

import os, sys
sys.path.insert(0, "..")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "test_sqlite_msgpack")

if __name__ == "__main__":
    from django.core.management import execute_from_command_line
    args = sys.argv
    args.insert(1, "test")

    execute_from_command_line(args)
