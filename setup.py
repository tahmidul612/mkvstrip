#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Note: To use the 'upload' functionality of this file, you must:
# $ pip install twine

from setuptools import setup, Command  # find_packages
from shutil import rmtree
import sys
import io
import os
import re

# Package meta-data.
VERSION = None
NAME = "mkvstrip"
URL = "https://github.com/willforde/mkvstrip"
EMAIL = "willforde@gmail.com"
AUTHOR = "William Forde"
REQUIRES_PYTHON = ">=3.4.0"
KEYWORDS = "mkv mkvmerge mkvtoolnix"
PLATFORMS = ["OS Independent"]
DESCRIPTION = "Python script, that acts as a front end for mkvtoolnix to remove" \
              "excess audio and subtitle streams from mkv files."

# Trove classifiers
# Full list: https://pypi.python.org/pypi?%3Aaction=list_classifiers
CLASSIFIERS = [
    "Development Status :: 5 - Production/Stable",
    "Intended Audience :: End Users/Desktop",
    "Operating System :: OS Independent",
    "Environment :: Console",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.4",
    "Programming Language :: Python :: 3.5",
    "Programming Language :: Python :: 3.6",
    "Topic :: Multimedia :: Sound/Audio",
    "Topic :: Multimedia :: Video",
    "Topic :: Utilities"
    ]

# License information, GPLv3, MIT
LICENSE = "GPLv3"
CLASSIFIERS.append("License :: OSI Approved :: GNU General Public License v3 (GPLv3)")

# What packages are required for this module to be executed?
# e.g. REQUIRED = ['requests', 'maya', 'records']
REQUIRED = []


# The rest you shouldn't have to touch too much.
# Except, perhaps the package type, e.g. py_modules, entry_points, packages.
# ##########################################################################
here = os.path.abspath(os.path.dirname(__file__))

# Import the README and use it as the long-description.
# Note: this will only work if 'README.rst' is present in your MANIFEST.in file!
with io.open(os.path.join(here, "README.rst"), encoding="utf-8") as stream:
    long_description = "\n" + stream.read()

# Load the package's __version__.py module as a dictionary.
if not VERSION:
    paths = [os.path.join(here, "{}.py".format(NAME)),
             os.path.join(here, NAME, "__init__.py"),
             os.path.join(here, NAME, "__version__.py")]

    for path in paths:
        if os.path.exists(path):
            with io.open(path, "r", encoding="utf-8") as stream:
                search_refind = '_{0,2}version_{0,2} = ["\'](\d+\.\d+\.\d+)["\']'
                match = re.search(search_refind, stream.read(), flags=re.IGNORECASE)
                if match:
                    VERSION = match.group(1)
                    break
    else:
        raise RuntimeError("Version number is required, Unable to extract from package")


class UploadCommand(Command):
    """Support setup.py upload."""
    description = "Build and publish the package."
    user_options = []

    @staticmethod
    def status(s):
        """Prints things in bold."""
        print('\033[1m{0}\033[0m'.format(s))

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        try:
            self.status("Removing previous builds...")
            rmtree(os.path.join(here, "dist"))
        except OSError:
            pass

        self.status("Building Source and Wheel (universal) distribution...")
        os.system("{0} setup.py sdist bdist_wheel --universal".format(sys.executable))

        self.status("Uploading the package to PyPi via Twine...")
        os.system("twine upload dist/*")

        self.status("Pushing git tags...")
        os.system("git tag v{0}".format(VERSION))
        os.system("git push --tags")

        sys.exit()


# Where the magic happens:
setup(
    url=URL,
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=long_description,
    author=AUTHOR,
    LICENSE=LICENSE,
    keywords=KEYWORDS,
    platforms=PLATFORMS,
    author_email=EMAIL,
    python_requires=REQUIRES_PYTHON,
    install_requires=REQUIRED,
    include_package_data=True,
    cmdclass={"upload": UploadCommand},
    classifiers=CLASSIFIERS,

    # If project is a single module, use:
    py_modules=["mkvstrip"],

    # If project is a package, use:
    # packages=find_packages(exclude=("tests",)),

    # If project is a script, use
    entry_points={"console_scripts": ["mkvstrip=mkvstrip:main"]}
    )
