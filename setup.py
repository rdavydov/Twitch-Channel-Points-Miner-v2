from os import path

import setuptools
import re


def read(fname):
    return open(path.join(path.dirname(__file__), fname), encoding="utf-8").read()


metadata = dict(
    re.findall(
        r"""__([a-z]+)__ = "([^"]+)""", read("TwitchChannelPointsMiner/__init__.py")
    )
)

setuptools.setup(
    name="Twitch-Channel-Points-Miner-v2",
    version=metadata["version"],
    author="Tkd-Alex (Alessandro Maggio) and rdavydov (Roman Davydov)",
    author_email="alex.tkd.alex@gmail.com",
    description="A simple script that will watch a stream for you and earn the channel points.",
    license="GPLv3+",
    keywords="python bot streaming script miner twtich channel-points",
    url="https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2",
    packages=setuptools.find_packages(),
    include_package_data=True,
    install_requires=[
        "requests",
        "websocket-client",
        "pillow",
        "python-dateutil",
        "emoji",
        "millify",
        "pre-commit",
        "colorama",
        "flask",
        "irc",
        "pandas",
        "pytz"
    ],
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Operating System :: OS Independent",
        "Topic :: Utilities",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering",
        "Topic :: Software Development :: Version Control :: Git",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Natural Language :: English",
    ],
    python_requires=">=3.6",
)
