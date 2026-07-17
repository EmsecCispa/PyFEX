from setuptools import setup, find_packages

setup(
    name='byted-df',
    version='99.1.1',
    author='j3ssie-bd',
    author_email='ho.jessie@bytedance.com',
    description='A simple project that act as a placeholder for project name',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'byted-df=byted_df:byted_df',
        ],
    },
)