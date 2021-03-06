#!/usr/bin/env python
# coding=utf-8
from setuptools import setup, find_packages

setup(
    name = "Climatedsl",
    version = "0.0.1b0",
    packages = find_packages(),
    install_requires = [
        "numpy<1.12", #NOTE: this is for testing purposes only as the original PyOM does not support numpy 1.12
        "scipy",
        "pyamg",
        "netCDF4"
        ],
    author = "René Løwe Jacobsen",
    author_email = "rlj@rloewe.net",
    scripts = [
	"climate/scripts/create_mask.py"
	]
)
