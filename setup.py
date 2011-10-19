#!/usr/bin/env python

"""
@file setup.py
@see http://peak.telecommunity.com/DevCenter/setuptools
"""

setupdict = {
    'name' : 'epuagent',
    'version' : '1.1.1',
    'description' : 'OOICI CEI Elastic Processing Unit Agents',
    'url': 'https://confluence.oceanobservatories.org/display/CIDev/Common+Execution+Infrastructure+Development',
    'download_url' : 'http://ooici.net/packages',
    'license' : 'Apache 2.0',
    'author' : 'CEI',
    'author_email' : 'labisso@uchicago.edu',
    'keywords': ['ooici','cei','epu'],
    'classifiers' : [
    'Development Status :: 3 - Alpha',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: Apache Software License',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'Topic :: Scientific/Engineering'],
}

from setuptools import setup, find_packages
setupdict['packages'] = find_packages()

setupdict['dependency_links'] = ['http://ooici.net/releases']
setupdict['test_suite'] = 'epuagent'
#setupdict['include_package_data'] = True
#setupdict['package_data'] = {
#    'epu': ['data/*.sqlt', 'data/install.sh']
setupdict['install_requires'] = ['ioncore<1.2']

setup(**setupdict)
