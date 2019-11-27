import os
import re

import setuptools
from pkg_resources import parse_requirements
from setuptools import find_packages

base_path = os.path.dirname(__file__)

with open(os.path.join(base_path, 'README.md')) as readme:
    README = readme.read()

os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

packages = find_packages()


def get_reqs(lines):
    return [str(r) for r in parse_requirements(lines)]


def get_requirements(req_path, exclude=None):
    if exclude is None:
        exclude = []
    reqs = []
    dir_name = os.path.dirname(req_path)
    with open(req_path) as requirements:
        pattern = re.compile("-r (.+)")
        for line in requirements.readlines():
            match = pattern.match(line)
            if match:
                dep_reqs = os.path.join(dir_name, match.group(1))
                with open(dep_reqs) as dep_requirements:
                    for dep_line in dep_requirements.readlines():
                        reqs.append(dep_line.rstrip())
                reqs += get_requirements(dep_reqs, exclude=exclude)
                continue
            package = line.rstrip()
            if package not in exclude:
                reqs.append(package)
    return reqs


exclude_packages = []
reqs = get_requirements(os.path.join(base_path, 'requirements.txt'), exclude=exclude_packages)

setuptools.setup(
    name="afbmq",
    version="0.0.1",
    author_email="yurmarkin97@gmail.com",
    description="Python asyncio facebook messenger",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/aiogram/aVKapi",
    packages=setuptools.find_packages(),
    install_requires=reqs,
    classifiers=(
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Framework :: AsyncIO",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.7",
    ),
)
