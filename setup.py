import os

from setuptools import find_packages, setup


def get_version():
    basedir = os.path.dirname(__file__)
    with open(os.path.join(basedir, 'rqmonitor/version.py')) as f:
        locals = {}
        exec(f.read(), locals)
        return locals['VERSION']


with open("README.md", "r") as fh:
    long_description = fh.read()


setup(
    name='rqmonitor',
    version=get_version(),
    author="Pranav Gupta",
    author_email="pranavgupta4321@gmail.com",
    description="Flask based dynamic and actionable dashboard for monitoring RQs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/pranavgupta1234/rqmonitor",
    download_url="https://github.com/pranavgupta1234/rqmonitor/archive/v_1.0.0.tar.gz",
    license="Apache Software License",
    packages=find_packages(exclude=('tests',)),
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=[
        'redis>=3.3.11',
        'humanize>=2.4.0',
        'Flask>=1.1.1',
        'Click>=7.0',
        'six>=1.13.0',
        'Werkzeug>=0.16.0',
        'rq>=1.2.0',
        'fabric>=2.5.0',
        'invoke>=1.4.1',
    ],
    entry_points={
        'console_scripts': [
            'rqmonitor = rqmonitor.cli:main'
        ]
    },
    classifiers=[
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        'License :: OSI Approved :: Apache Software License',

        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
 )
