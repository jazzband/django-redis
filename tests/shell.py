# -*- coding: utf-8 -*-

import os, sys
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "test_sqlite")
sys.path.insert(0, '..')

if __name__ == "__main__":
    from django.core.management import execute_from_command_line
    args = sys.argv
    args.insert(1, "shell")

    execute_from_command_line(args)
