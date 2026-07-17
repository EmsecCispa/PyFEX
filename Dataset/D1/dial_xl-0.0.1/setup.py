from setuptools import setup, find_packages

setup(
    name='dial-xl',
    version='0.0.1',
    description='Distributed Identity & Access Layer for XL-scale environments',
    long_description=open("README.md").read(),
    long_description_content_type='text/markdown',
    author='XL Identity Org',
    author_email='security@xl-id.org',
    url='https://github.com/xl-id/dial-xl',
    license='MIT',
    packages=find_packages(),
    include_package_data=True,
    python_requires='>=3.6',
)
