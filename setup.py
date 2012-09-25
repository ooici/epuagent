#!/usr/bin/env python

"""
@file setup.py
@see http://peak.telecommunity.com/DevCenter/setuptools
"""

version = '1.1.2'

setupdict = {
    'name' : 'epuagent',
    'version' : version,
    'description' : 'OOICI CEI Elastic Processing Unit Agents',
    'url': 'https://confluence.oceanobservatories.org/display/CIDev/Common+Execution+Infrastructure+Development',
    'download_url' : 'http://sddevrepo.oceanobservatories.org/releases',
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

setupdict['dependency_links'] = ['http://ssdevrepo.oceanobservatories.org/releases']
setupdict['test_suite'] = 'epuagent'
#setupdict['include_package_data'] = True
#setupdict['package_data'] = {
#    'epu': ['data/*.sqlt', 'data/install.sh']
setupdict['install_requires'] = ['gevent==0.13.7',
                                 'dashi==0.1',
                                 'supervisor==3.0a10',
                                 'nose']

setupdict['entry_points'] = {
        'console_scripts': [
            'epu-agent=epuagent.agent:main',
            ]
        }
setupdict['package_data'] = {'epuagent': ['config/*.yml']}

setup(**setupdict)
