cmake_minimum_required(VERSION 3.15)
project(nrpc_ts VERSION 1.0.1)

###################
# Common settings #
###################
    string(ASCII 27 Esc)
    set(Reset "${Esc}[m")
    set(Yellow      "${Esc}[33m")
    message(STATUS "${Yellow}Common settings${Reset}")
    set(CMAKE_WARN_DEPRECATED OFF CACHE BOOL "" FORCE)
    set(Bold  "${Esc}[1m")
    set(Red         "${Esc}[31m")
    set(Green       "${Esc}[32m")
    set(Blue        "${Esc}[34m")
    set(Magenta     "${Esc}[35m")
    cmake_policy(SET CMP0169 OLD)

######################
# Fetch dependencies #
######################
    message(STATUS "${Yellow}Fetch dependencies${Reset}")
    enable_language(CXX)
    enable_language(C)
    include(FetchContent)
    include(CMakePackageConfigHelpers)
    FetchContent_Declare(pyzmq
        GIT_REPOSITORY "https://github.com/zeromq/pyzmq.git"
        GIT_TAG "origin/main" 
        SOURCE_DIR "${CMAKE_CURRENT_LIST_DIR}/staging_modules/pyzmq"
        EXCLUDE_FROM_ALL
    )
    FetchContent_GetProperties(pyzmq)
    if(NOT pyzmq_POPULATED)
        FetchContent_Populate(pyzmq)
    endif()

######################
# Patch dependencies #
######################
    message(STATUS "${Yellow}Patch dependencies${Reset}")
    file(READ "staging_modules/pyzmq/zmq/backend/cython/_zmq.pxd" contents1)
    file(READ "staging_modules/pyzmq/zmq/backend/cython/_zmq.py" contents2)
    if(NOT "${contents1}" MATCHES "# NRPC-PY")
        file(WRITE 
            "staging_modules/pyzmq/zmq/backend/cython/_zmq.pxd"
            "${contents1}"
            " \n"
            "# NRPC-PY: Extra helper from draft functionality.\n"
            "cdef extern from \"zmq.h\" nogil:\n"
            "    # MUST BUILD WITH ZMQ_DRAFT_API ENABLED. See nrpc-py/CMakeLists.txt.\n"
            "    int zmq_socket_get_peer_state (void *socket, const void *routing_id, size_t routing_size)\n"
            "# NRPC-PY: End.\n"
        )
    endif()
    if(NOT "${contents2}" MATCHES "# NRPC-PY")
        file(WRITE 
            "staging_modules/pyzmq/zmq/backend/cython/_zmq.py"
            "${contents2}"
            " \n"
            "# NRPC-PY: Extra helper from draft functionality.\n"
            "def _zmq_socket_get_peer_state(socket: Socket, routing: bytes):\n"
            "   socket_ptr: p_void = NULL\n"
            "   routing_buf: p_char = NULL\n"
            "   routing_len: Py_ssize_t = 0\n"
            "   asbuffer_r(routing, cast(pointer(p_void), address(routing_buf)), address(routing_len))\n"
            "   socket_ptr = socket.handle\n"
            "   rc = zmq_socket_get_peer_state(socket_ptr, routing_buf, routing_len)\n"
            "   if rc == -1:\n"
            "       err_text = zmq.strerror(zmq.zmq_errno())\n"
            "   return rc\n"
            "__all__.append('_zmq_socket_get_peer_state')\n"
            "# NRPC-PY: End.\n"
        )
    endif()

######################
# Build dependencies #
######################
    message(STATUS "${Yellow}Build dependencies${Reset}")
    file(REMOVE_RECURSE staging_modules/pyzmq/dist)
    set(ENV{ZMQ_PREFIX} bundled)
    set(ENV{CMAKE_GENERATOR_PLATFORM} x64)
    set(ENV{ZMQ_DRAFT_API} ON)
    execute_process(
        COMMAND cmd /c python -m build
        WORKING_DIRECTORY  ${CMAKE_CURRENT_LIST_DIR}/staging_modules/pyzmq
        RESULT_VARIABLE result_var
    )
    if(NOT "${result_var}" STREQUAL "0")
        message(FATAL_ERROR "Failed with code: ${result_var}")
    endif()

#########################
## Install dependencies #
#########################
    message(STATUS "${Yellow}Install dependencies${Reset}")
    execute_process(
        COMMAND
            cmd /C
                python -m
                    pip install --force-reinstall staging_modules/pyzmq/dist/pyzmq-26.3.0.dev0-cp313-cp313-win_amd64.whl
    )

