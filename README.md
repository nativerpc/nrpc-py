# Native RPC Communication Library

Cross-platform and cross-language communication library in Python. Part of larger [Native RPC](https://github.com/nativerpc) framework. See [README.md](https://github.com/nativerpc/nrpc-examples) in nrpc-examples project for more information.

# Prerequisites

Ensuring up-to-date python tooling.

```
pip install setuptools
pip install build packaging
pip install pytest colorama ipython
```

# Configuration and dependency build

Project configuration and dependency build.

```
cmake -B build
```

# Build and installation

Build and installation.

```
python -m build
pip install -e .
```

# Manual and automated tests

Manual and automated tests.

```
pytest
python test\test_show.py
python test\test_array.py
etc
```

# Alternative builds

Alternative PyZmq build. 

```
cd staging_modules/pyzmq
set ZMQ_PREFIX=bundled
set CMAKE_GENERATOR_PLATFORM=x64
set ZMQ_DRAFT_API=ON
python -m build
```

Alternative PyZmq build.
```
cd staging_modules/pyzmq
cmake -B build -DZMQ_PREFIX=bundled -DCMAKE_GENERATOR_PLATFORM=x64 -DZMQ_DRAFT_API=ON
```

Alternative PyZmq install.
```
cd staging_modules/pyzmq
pip install dist/pyzmq-26.3.0.dev0-cp313-cp313-win_amd64.whl --force-reinstall
```

Alternative PyZmq install. 
```
cd staging_modules/pyzmq
pip install -e .
```
