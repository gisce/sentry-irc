#!/usr/bin/env python
"""
sentry-irc
==============

An extension for Sentry which integrates with IRC. It will send
notifications to IRC rooms.

:copyright: (c) 2012 by Eduard Carreras, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""
from setuptools import setup, find_packages


tests_require = [
    'nose>=1.1.2',
]

install_requires = [
    'sentry>=3.8.0',
]

setup(
    name='sentry-irc',
    version='0.1.0',
    author='Eduard Carreras',
    author_email='ecarreras@gisce.net',
    url='http://code.gisce.net/sentry-irc',
    description='A Sentry extension which integrates with IRC',
    long_description=__doc__,
    license='BSD',
    packages=find_packages(exclude=['tests']),
    zip_safe=False,
    install_requires=install_requires,
    tests_require=tests_require,
    extras_require={'test': tests_require},
    test_suite='runtests.runtests',
    include_package_data=True,
    classifiers=[
        'Framework :: Django',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Operating System :: OS Independent',
        'Topic :: Software Development'
    ],
)
