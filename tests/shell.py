# -*- coding: utf-8 -*-

import os, sys
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "test_sqlite_failover")
sys.path.insert(0, '..')

from django.core.management import call_command

if __name__ == "__main__":
    args = sys.argv[1:]
    call_command("shell")
