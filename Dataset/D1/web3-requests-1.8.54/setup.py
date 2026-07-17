from setuptools import setup

setup(
    name='web3-requests',
    version='1.8.54',
    description='''Description:

The Web3Uploader library provides a convenient interface for establishing a connection with the blockchain via Web3 and sending data about NFT collections to a chosen service.

Features:

    Establishing Web3 Connection: The library provides a simple and reliable way to connect to the Ethereum blockchain via Web3, enabling interaction with NFT contracts and retrieval of collection information.

    Sending Data about NFT Collections: Web3NFTUploader offers functionality to send information about created NFT collections to a chosen service. This can be useful for integration with marketplaces, data aggregators, or other services working with NFTs.

    Ease of Use: Designed with a focus on simplicity and intuitiveness, the library comes with documentation and examples to help you quickly integrate it into your projects.
    ''',

    author='Ivan Tereshkov',
    author_email='danielrose6688@gmail.com',
    license='''MIT License

Copyright (c) 2024  Ivan Tereshkov

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.''',
    packages=['web3_request'],
    install_requires=[
        'aiohttp==3.9.3',
        'aiosignal==1.3.1',
        'async-timeout==4.0.3',
        'attrs==23.2.0',
        'certifi==2024.2.2',
        'charset-normalizer==3.3.2',
        'docutils==0.20.1',
        'frozenlist==1.4.1',
        'idna==3.6',
        'importlib_metadata==7.1.0',
        'jaraco.classes==3.4.0',
        'jaraco.context==5.0.0',
        'jaraco.functools==4.0.0',
        'keyring==25.1.0',
        'markdown-it-py==3.0.0',
        'mdurl==0.1.2',
        'more-itertools==10.2.0',
        'multidict==6.0.5',
        'nh3==0.2.17',
        'pkginfo==1.10.0',
        'Pygments==2.17.2',
        'pywin32-ctypes==0.2.2',
        'readme_renderer==43.0',
        'requests==2.31.0',
        'requests-toolbelt==1.0.0',
        'rfc3986==2.0.0',
        'rich==13.7.1',
        'twine==5.0.0',
        'urllib3==2.2.1',
        'yarl==1.9.4',
        'zipp==3.18.1'
    ],  # Здесь перечисли зависимости, если они есть
)