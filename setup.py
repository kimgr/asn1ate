#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

try:
    from setuptools import setup
except:
    from distutils.core import setup


def get_version():
    version_file = os.path.join(os.path.dirname(__file__),
                                'asn1ate', '__init__.py')

    environment = {}
    with open(version_file) as fp:
        exec(fp.read(), environment)

    return environment['__version__']


setup(
    name='asn1ate',
    version=get_version(),
    description='ASN.1 translation library.',
    author='Kim Gräsman',
    author_email='kim.grasman@gmail.com',
    license='BSD',
    long_description=open('README.txt').read(),
    url='http://github.com/kimgr/asn1ate',
    packages=[
        'asn1ate',
        'asn1ate.support',
    ],
    platforms=['any'],
    install_requires=[
        'pyparsing >=2.0.0, !=3.0.5, !=3.0.6',
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Code Generators',
    ],
    entry_points={
        'console_scripts': [
            'asn1ate = asn1ate.pyasn1gen:main_cli'
        ]
    }
)
