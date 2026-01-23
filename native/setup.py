"""
Python C Extension 빌드 스크립트

이 스크립트는 USN Journal 스캐너 C/C++ 코드를
Python 확장 모듈로 빌드합니다.

빌드 방법:
    python setup.py build_ext --inplace

설치 방법:
    python setup.py install
"""

from setuptools import setup, Extension
import sys
import os

# pybind11 import 제거 (사용하지 않음)

# 프로젝트 루트 디렉토리 (setup.py가 있는 디렉토리)
base_dir = os.path.dirname(os.path.abspath(__file__))

# Windows용 컴파일러 설정
if sys.platform == 'win32':
    extra_compile_args = ['/std:c++17', '/O2', '/MD', '/EHsc']
    extra_link_args = []
    libraries = ['kernel32']
else:
    extra_compile_args = ['-std=c++17', '-O3']
    extra_link_args = []
    libraries = []

# C++ 확장 모듈 정의
ext_modules = [
    Extension(
        'usn_scanner_native',
        sources=[
            os.path.join(base_dir, 'usn_scanner.cpp'),
            os.path.join(base_dir, 'python_bindings.cpp')
        ],
        include_dirs=[base_dir],
        language='c++',
        extra_compile_args=extra_compile_args,
        extra_link_args=extra_link_args,
        libraries=libraries,
        define_macros=[('PY_SSIZE_T_CLEAN', None)]
    ),
    Extension(
        'memory_index_native',
        sources=[
            os.path.join(base_dir, 'memory_index.cpp'),
            os.path.join(base_dir, 'memory_index_bindings.cpp')
        ],
        include_dirs=[base_dir],
        language='c++',
        extra_compile_args=extra_compile_args,
        extra_link_args=extra_link_args,
        libraries=libraries,
        define_macros=[('PY_SSIZE_T_CLEAN', None)]
    )
]

setup(
    name='usn_scanner_native',
    version='1.0.0',
    description='High-performance USN Journal scanner for Windows',
    ext_modules=ext_modules,
    zip_safe=False,
    python_requires='>=3.8',
)

