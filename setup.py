#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name='tap-paycor',
      version='0.0.1',
      description='Singer.io tap for extracting data from Paycor',
      classifiers=['Programming Language :: Python :: 3 :: Only'],
      py_modules=['tap_paycor'],
      install_requires=[
          'singer-python==5.12.1',
          'requests==2.20.0',
          'backoff==1.8.0'
      ],
      entry_points='''
          [console_scripts]
          tap-paycor=tap_paycor:main
      ''',
      packages=find_packages(),
      package_data = {
          'tap_paycor/schemas': [
              'employees.json'
          ],
      },
      include_package_data=True
)