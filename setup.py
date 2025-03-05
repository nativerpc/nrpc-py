from setuptools import setup

setup(
    name='nrpc-py',
    version='1.0.1',
    packages=[
        'nrpc_py'
    ],
    install_requires=[
        'pyzmq',
    ],
    author='Aare Pikaro',
    author_email='aare.pikaro@example.com',
    description='Native RPC communication library',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='http://github.com/aarepikaro/nrpc-py',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6'
)
