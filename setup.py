import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setuptools.setup(
    name='rqmonitor',
    version='0.0.3',
    author="Pranav Gupta",
    author_email="pranavgupta4321@gmail.com",
    description="Flask based dynamic and actionable dashboard for monitoring RQs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/pranavgupta1234/rqmonitor",
    download_url="https://github.com/pranavgupta1234/rqmonitor/archive/v_0.0.1.tar.gz",
    license="Apache Software License",
    packages=["rqmonitor"],
    install_requires=requirements,
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
