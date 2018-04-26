from setuptools import setup
from os import path
import re


def readme():
    # Get the long description from the README file
    readme_file = path.join(path.abspath(path.dirname(__file__)), "README.rst")
    with open(readme_file, "r") as opened_file:
        return opened_file.read()


def version(name):
    with open(name, 'rb') as opened:
        search_refind = b'__version__ = ["\'](\d+\.\d+\.\d+)["\']'
        verdata = re.search(search_refind, opened.read())
        if verdata:
            data = verdata.group(1)
            return data.decode()
        else:
            raise RuntimeError("Unable to extract version number")


setup(name='mkvstrip',
      version=version('mkvstrip.py'),
      description='Python script, that acts as a front end for mkvtoolnix to remove'
                  'excess audio and subtitle streams from mkv files.',
      long_description=readme(),
      #keywords='url lightweight caching http-client requests',
      classifiers=[#'Development Status :: 4 - Beta',
                   #'Intended Audience :: Developers',
                   #'License :: OSI Approved :: MIT License',
                   #'Natural Language :: English',
                   'Operating System :: OS Independent',
                   'Programming Language :: Python :: 3',
                   'Programming Language :: Python :: 3.4',
                   'Programming Language :: Python :: 3.5',
                   'Programming Language :: Python :: 3.6',
                   #'Topic :: Internet :: WWW/HTTP',
                   #'Topic :: Software Development :: Libraries :: Python Modules'
          ],
      url='https://github.com/willforde/mkvstrip/tree/master',
      platforms=['OS Independent'],
      author='William Forde',
      author_email='willforde@gmail.com',
      #license='MIT License',
      #py_modules=['urlquick'])
