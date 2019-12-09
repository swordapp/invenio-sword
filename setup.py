# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2015, 2016, 2017 CERN.
#
# Invenio is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.
"""Module for depositing record metadata and uploading files."""
import os

from setuptools import find_packages
from setuptools import setup

readme = open("README.rst").read()
history = open("CHANGES.rst").read()

tests_require = [
    # 'check-manifest>=0.25',
    # 'coverage>=4.0',
    # 'invenio-access>=1.0.0',
    # 'invenio-accounts>=1.0.0',
    # 'invenio-db[postgresql]>=1.0.1',
    # 'isort>=4.2.2',
    # 'pydocstyle>=1.0.0',
    # 'pytest-cache>=1.0',
    # 'pytest-cov>=1.8.0',
    # 'pytest-pep8>=1.0.6',
    # 'pytest>=3.0.4',
    # 'reportlab>=3.3.0',
]

invenio_search_version = "1.2.0"

extras_require = {
    # 'docs': [
    #     'Sphinx>=1.5.1',
    # ],
    # 'elasticsearch2': [
    #     'invenio-search[elasticsearch2]>={}'.format(invenio_search_version),
    # ],
    # 'elasticsearch5': [
    #     'invenio-search[elasticsearch5]>={}'.format(invenio_search_version),
    # ],
    # 'elasticsearch6': [
    #     'invenio-search[elasticsearch6]>={}'.format(invenio_search_version),
    # ],
    # 'elasticsearch7': [
    #     'invenio-search[elasticsearch7]>={}'.format(invenio_search_version),
    # ],
    # 'tests': tests_require,
}


extras_require["all"] = []
for name, reqs in extras_require.items():
    if name in (
        "sqlite",
        "elasticsearch2",
        "elasticsearch5",
        "elasticsearch6",
        "elasticsearch7",
    ):
        continue
    extras_require["all"].extend(reqs)

setup_requires = [
    "Babel>=1.3",
    "pytest-runner>=2.6.2",
]

install_requires = [
    "Flask-BabelEx>=0.9.3",
    "Flask-Login>=0.3.2",
    "Flask>=0.11.1",
    "SQLAlchemy-Continuum>=1.3.6",
    "SQLAlchemy-Utils[encrypted]>=0.33",
    "dictdiffer>=0.5.0.post1",
    "invenio-assets>=1.0.0",
    "invenio-db[versioning]>=1.0.1",
    "invenio-deposit>=1.0.0a1",
    "invenio-files-rest>=1.0.1",
    "invenio-jsonschemas>=1.0.0a3",
    "invenio-oauth2server>=1.0.3",
    "invenio-records-files>=1.0.0a10",
    "invenio-records-rest>=1.5.0",
    "invenio-records-ui>=1.0.1",
    "invenio-search-ui>=1.0.0a5",
    "rfc6266-parser",
]

packages = find_packages()


# Get the version string. Cannot be done with import!
g = {}
with open(os.path.join("invenio_sword", "version.py"), "rt") as fp:
    exec(fp.read(), g)
    version = g["__version__"]

setup(
    name="invenio-sword",
    version=version,
    description=__doc__,
    long_description=readme + "\n\n" + history,
    long_description_content_type="text/x-rst",
    keywords="invenio sword deposit upload",
    license="GPLv2",
    author="CERN",
    author_email="info@inveniosoftware.org",
    url="https://github.com/inveniosoftware/invenio-sword",
    packages=packages,
    zip_safe=False,
    include_package_data=True,
    platforms="any",
    entry_points={
        "invenio_base.apps": [
            "invenio_sword_wellknown = invenio_sword:InvenioSwordWellKnown",
        ],
        "invenio_base.api_apps": ["invenio_sword = invenio_sword:InvenioSword",],
        "invenio_sword.packaging": [
            "http://purl.org/net/sword/3.0/package/Binary = invenio_sword.packaging:BinaryPackaging",
            "http://purl.org/net/sword/3.0/package/SimpleZip = invenio_sword.packaging:SimpleZipPackaging",
            "http://purl.org/net/sword/3.0/package/SWORDBagIt = invenio_sword.packaging:SWORDBagItPackaging",
        ],
    },
    extras_require=extras_require,
    install_requires=install_requires,
    setup_requires=setup_requires,
    tests_require=tests_require,
    classifiers=[
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: Implementation :: CPython",
        "Development Status :: 1 - Planning",
    ],
)
