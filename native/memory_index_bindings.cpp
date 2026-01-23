/*
 * 메모리 인덱스 Python 바인딩
 * 
 * C++ 메모리 인덱스를 Python에서 사용할 수 있도록 래핑
 */

#include <Python.h>
#include "memory_index.h"
#include <structmember.h>

// MemoryIndex Python 객체
typedef struct {
    PyObject_HEAD
    MemoryIndexHandle handle;
} PyMemoryIndex;

// MemoryIndex 객체 해제
static void PyMemoryIndex_dealloc(PyMemoryIndex* self) {
    if (self->handle) {
        destroy_memory_index(self->handle);
        self->handle = nullptr;
    }
    Py_TYPE(self)->tp_free((PyObject*)self);
}

// MemoryIndex 객체 생성
static PyObject* PyMemoryIndex_new(PyTypeObject* type, PyObject* args, PyObject* kwds) {
    PyMemoryIndex* self = (PyMemoryIndex*)type->tp_alloc(type, 0);
    if (self) {
        self->handle = create_memory_index();
        if (!self->handle) {
            Py_DECREF(self);
            return PyErr_NoMemory();
        }
    }
    return (PyObject*)self;
}

// add_file 메서드
static PyObject* PyMemoryIndex_add_file(PyMemoryIndex* self, PyObject* args) {
    PyObject* path_obj, *name_obj, *ext_obj;
    unsigned long long size;
    long long modified_time;
    int is_directory;
    
    if (!PyArg_ParseTuple(args, "UUUKLi", 
                          &path_obj, &name_obj, &ext_obj,
                          &size, &modified_time, &is_directory)) {
        return NULL;
    }
    
    wchar_t* path = PyUnicode_AsWideCharString(path_obj, NULL);
    wchar_t* name = PyUnicode_AsWideCharString(name_obj, NULL);
    wchar_t* ext = PyUnicode_AsWideCharString(ext_obj, NULL);
    
    if (!path || !name || !ext) {
        if (path) PyMem_Free(path);
        if (name) PyMem_Free(name);
        if (ext) PyMem_Free(ext);
        return PyErr_NoMemory();
    }
    
    memory_index_add_file(self->handle, path, name, ext, size, modified_time, is_directory != 0);
    
    PyMem_Free(path);
    PyMem_Free(name);
    PyMem_Free(ext);
    
    Py_RETURN_NONE;
}

// build 메서드
static PyObject* PyMemoryIndex_build(PyMemoryIndex* self, PyObject* args) {
    memory_index_build(self->handle);
    Py_RETURN_NONE;
}

// search 메서드
static PyObject* PyMemoryIndex_search(PyMemoryIndex* self, PyObject* args) {
    PyObject* query_obj;
    Py_ssize_t max_results = 1000;
    
    if (!PyArg_ParseTuple(args, "U|n", &query_obj, &max_results)) {
        return NULL;
    }
    
    wchar_t* query = PyUnicode_AsWideCharString(query_obj, NULL);
    if (!query) {
        return PyErr_NoMemory();
    }
    
    SearchResult* result = memory_index_search(self->handle, query, max_results);
    PyMem_Free(query);
    
    if (!result) {
        return PyList_New(0);
    }
    
    // 결과를 Python 리스트로 변환
    PyObject* result_list = PyList_New(result->count);
    if (!result_list) {
        memory_index_free_search_result(self->handle, result);
        return NULL;
    }
    
    for (size_t i = 0; i < result->count; i++) {
        PyList_SetItem(result_list, i, PyLong_FromUnsignedLong(result->indices[i]));
    }
    
    memory_index_free_search_result(self->handle, result);
    return result_list;
}

// get_file_info 메서드
static PyObject* PyMemoryIndex_get_file_info(PyMemoryIndex* self, PyObject* args) {
    Py_ssize_t index;
    
    if (!PyArg_ParseTuple(args, "n", &index)) {
        return NULL;
    }
    
    wchar_t path_buf[MAX_PATH];
    wchar_t name_buf[MAX_PATH];
    wchar_t ext_buf[32];
    uint64_t size;
    int64_t modified_time;
    
    if (!memory_index_get_file_info(
            self->handle, index,
            path_buf, MAX_PATH,
            name_buf, MAX_PATH,
            ext_buf, 32,
            &size, &modified_time)) {
        PyErr_SetString(PyExc_IndexError, "File index out of range");
        return NULL;
    }
    
    PyObject* result = PyDict_New();
    PyDict_SetItemString(result, "path", PyUnicode_FromWideChar(path_buf, -1));
    PyDict_SetItemString(result, "name", PyUnicode_FromWideChar(name_buf, -1));
    PyDict_SetItemString(result, "extension", PyUnicode_FromWideChar(ext_buf, -1));
    PyDict_SetItemString(result, "size", PyLong_FromUnsignedLongLong(size));
    PyDict_SetItemString(result, "modified_time", PyLong_FromLongLong(modified_time));
    
    return result;
}

// save_snapshot 메서드
static PyObject* PyMemoryIndex_save_snapshot(PyMemoryIndex* self, PyObject* args) {
    PyObject* path_obj;
    
    if (!PyArg_ParseTuple(args, "U", &path_obj)) {
        return NULL;
    }
    
    wchar_t* path = PyUnicode_AsWideCharString(path_obj, NULL);
    if (!path) {
        return PyErr_NoMemory();
    }
    
    bool success = memory_index_save_snapshot(self->handle, path);
    PyMem_Free(path);
    
    if (success) {
        Py_RETURN_TRUE;
    } else {
        Py_RETURN_FALSE;
    }
}

// load_snapshot 메서드
static PyObject* PyMemoryIndex_load_snapshot(PyMemoryIndex* self, PyObject* args) {
    PyObject* path_obj;
    
    if (!PyArg_ParseTuple(args, "U", &path_obj)) {
        return NULL;
    }
    
    wchar_t* path = PyUnicode_AsWideCharString(path_obj, NULL);
    if (!path) {
        return PyErr_NoMemory();
    }
    
    bool success = memory_index_load_snapshot(self->handle, path);
    PyMem_Free(path);
    
    if (success) {
        Py_RETURN_TRUE;
    } else {
        Py_RETURN_FALSE;
    }
}

// get_file_count 메서드
static PyObject* PyMemoryIndex_get_file_count(PyMemoryIndex* self, PyObject* args) {
    return PyLong_FromSize_t(memory_index_get_file_count(self->handle));
}

// get_memory_size 메서드
static PyObject* PyMemoryIndex_get_memory_size(PyMemoryIndex* self, PyObject* args) {
    return PyLong_FromSize_t(memory_index_get_memory_size(self->handle));
}

// clear 메서드
static PyObject* PyMemoryIndex_clear(PyMemoryIndex* self, PyObject* args) {
    memory_index_clear(self->handle);
    Py_RETURN_NONE;
}

// 메서드 정의
static PyMethodDef PyMemoryIndex_methods[] = {
    {"add_file", (PyCFunction)PyMemoryIndex_add_file, METH_VARARGS, "Add a file to the index"},
    {"build", (PyCFunction)PyMemoryIndex_build, METH_NOARGS, "Build the index for searching"},
    {"search", (PyCFunction)PyMemoryIndex_search, METH_VARARGS, "Search the index"},
    {"get_file_info", (PyCFunction)PyMemoryIndex_get_file_info, METH_VARARGS, "Get file information by index"},
    {"save_snapshot", (PyCFunction)PyMemoryIndex_save_snapshot, METH_VARARGS, "Save index to file"},
    {"load_snapshot", (PyCFunction)PyMemoryIndex_load_snapshot, METH_VARARGS, "Load index from file"},
    {"get_file_count", (PyCFunction)PyMemoryIndex_get_file_count, METH_NOARGS, "Get the number of indexed files"},
    {"get_memory_size", (PyCFunction)PyMemoryIndex_get_memory_size, METH_NOARGS, "Get memory usage in bytes"},
    {"clear", (PyCFunction)PyMemoryIndex_clear, METH_NOARGS, "Clear the index"},
    {NULL, NULL, 0, NULL}
};

// 타입 정의
static PyTypeObject PyMemoryIndexType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "memory_index_native.MemoryIndex",  // tp_name
    sizeof(PyMemoryIndex),              // tp_basicsize
    0,                                   // tp_itemsize
    (destructor)PyMemoryIndex_dealloc,  // tp_dealloc
    0,                                   // tp_print
    0,                                   // tp_getattr
    0,                                   // tp_setattr
    0,                                   // tp_reserved
    0,                                   // tp_repr
    0,                                   // tp_as_number
    0,                                   // tp_as_sequence
    0,                                   // tp_as_mapping
    0,                                   // tp_hash
    0,                                   // tp_call
    0,                                   // tp_str
    0,                                   // tp_getattro
    0,                                   // tp_setattro
    0,                                   // tp_as_buffer
    Py_TPFLAGS_DEFAULT,                  // tp_flags
    "MemoryIndex object",                // tp_doc
    0,                                   // tp_traverse
    0,                                   // tp_clear
    0,                                   // tp_richcompare
    0,                                   // tp_weaklistoffset
    0,                                   // tp_iter
    0,                                   // tp_iternext
    PyMemoryIndex_methods,               // tp_methods
    0,                                   // tp_members
    0,                                   // tp_getset
    0,                                   // tp_base
    0,                                   // tp_dict
    0,                                   // tp_descr_get
    0,                                   // tp_descr_set
    0,                                   // tp_dictoffset
    0,                                   // tp_init
    0,                                   // tp_alloc
    PyMemoryIndex_new,                   // tp_new
};

// 모듈 초기화
static PyModuleDef memory_index_module = {
    PyModuleDef_HEAD_INIT,
    "memory_index_native",
    "High-performance memory-based file index",
    -1,
    NULL, NULL, NULL, NULL, NULL
};

PyMODINIT_FUNC PyInit_memory_index_native(void) {
    PyObject* m;
    
    if (PyType_Ready(&PyMemoryIndexType) < 0) {
        return NULL;
    }
    
    m = PyModule_Create(&memory_index_module);
    if (m == NULL) {
        return NULL;
    }
    
    Py_INCREF(&PyMemoryIndexType);
    PyModule_AddObject(m, "MemoryIndex", (PyObject*)&PyMemoryIndexType);
    
    return m;
}

