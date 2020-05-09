import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='rqmonitor',
    version='0.0.1',
    author="Pranav Gupta",
    author_email="pranavgupta4321@gmail.com",
    description="Django based dynamic and actionable dashboard for monitoring RQs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/pranavgupta1234/rqmonitor",
    license="Apache Software License",
    packages=["rqmonitor"],
    classifiers=[
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        'License :: OSI Approved :: Apache Software License',

        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7'
    ],
 )