from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

# Get version from __version__ variable in enjo_party/__init__.py
from enjo_party import __version__ as version

setup(
    name="enjo_party",
    version=version,
    description="Party-Management für ENJO",
    author="Elia",
    author_email="elia@enjo.at",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires
) 