#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Holy Month AI - entrypoint.

This file is kept at the repo root, with the same name and the same
CLI commands (youtube-auth / create-plan / produce-today / web / test),
so the existing daily-video.yml workflow and any of your own scripts
keep working with zero changes.

All the actual logic now lives in the holy_month/ package (config, db,
agents, services, api) — this file just delegates to it.
"""
from holy_month.cli import main

if __name__ == "__main__":
    main()
