#!/usr/bin/env python
# -*- coding: utf-8 -*-

from distutils.core import setup

setup(
    name='asn1ate',
    version='0.4',
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
    requires=[
        'pyparsing (>=2.0.0)',
    ]
)
