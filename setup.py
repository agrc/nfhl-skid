#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
setup.py
A module that installs the nfhl-skid skid as a module
"""

from glob import glob
from os.path import basename, splitext

from setuptools import find_packages, setup

#: Load version from source file
version = {}
with open("src/nfhl/version.py") as fp:
    exec(fp.read(), version)

setup(
    name="nfhl-skid",
    version=version["__version__"],
    license="MIT",
    description="Update the DEM Flood Map data from FEMA's map services via GCF",
    author="Jacob Adams",
    author_email="jdadams@utah.gov",
    url="https://github.com/agrc/nfhl-skid",
    packages=find_packages("src"),
    package_dir={"": "src"},
    py_modules=[splitext(basename(path))[0] for path in glob("src/*.py")],
    include_package_data=True,
    zip_safe=True,
    classifiers=[
        # complete classifier list: http://pypi.python.org/pypi?%3Aaction=list_classifiers
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Utilities",
    ],
    project_urls={
        "Issue Tracker": "https://github.com/agrc/nfhl-skid/issues",
    },
    keywords=["gis"],
    install_requires=[
        "ugrc-palletjack>=5.0,<5.3",
        "ugrc-supervisor>=3.1.3",
        "arcgis==2.4.0",  #: Polygon dataframes aren't writing to gdb with 2.4.1.1
    ],
    extras_require={
        "tests": [
            "pytest-cov>=6",
            "pytest-instafail==0.5.*",
            "pytest-mock==3.*",
            "pytest-ruff==0.*",
            "pytest-watch==4.*",
            "pytest>=6,<9",
            "ruff==0.*",
            "functions-framework==3.8.*",
        ]
    },
    setup_requires=[
        "pytest-runner",
    ],
    entry_points={
        "console_scripts": [
            "nfhl-skid = nfhl.main:process",
        ]
    },
)
