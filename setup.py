from setuptools import setup, find_packages

setup(
    name='ShinySC',
    version='0.1.5',
    author='Kyle Lillie',
    description='This helps you build queries to download custom datatables from Statistics Canada. Ideal for use in data pipelines.',
    packages=find_packages(),
    classifiers=[
        'Programming Language :: Python 3',
        'License :: GPL-3.0-or-later'
    ],
    py_modules=['main'],
    python_requires='>=3.10',
    install_requires=[
        'requests>=2.28.0'
    ]
)