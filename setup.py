#!/usr/bin/env python

from setuptools import setup, find_packages

VERSION = "0.1"

setup(
    name="ArchiveDiscourse",
    version=VERSION,
    description="Archive a Discourse site.",
    url="https://github.com/tgr/ArchiveDiscourse",
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.6",
)
