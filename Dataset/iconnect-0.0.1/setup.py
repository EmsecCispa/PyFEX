from setuptools import setup, find_packages

setup(
    name='iconnect',
    version='0.0.1',
    description='Connectivity interface tools for asynchronous systems',
    long_description=open("README.md").read(),
    long_description_content_type='text/markdown',
    author='Informal Systems',
    author_email='support@informal.dev',
    url='https://github.com/informalsystems/iconnect',
    license='Apache 2.0',
    packages=find_packages(),
    include_package_data=True,
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)
