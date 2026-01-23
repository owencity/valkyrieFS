/*
 * Python C Extension 바인딩
 * 
 * USN Journal 스캐너를 Python에서 사용할 수 있도록
 * Python C API로 래핑합니다.
 */

#include <Python.h>
#include "usn_scanner.h"
#include <structmember.h>

// Python 파일 정보 구조체
typedef struct {
    PyObject_HEAD
    PyObject* path;
    PyObject* name;
    PyObject* extension;
    Py_ssize_t size;
    Py_ssize_t modified_time;
} PyFileInfo;

// FileInfoArray를 Python 리스트로 변환
static PyObject* file_info_array_to_list(FileInfoArray* array) {
    if (array == NULL || array->count == 0) {
        return PyList_New(0);  // 빈 리스트 반환
    }
    
    PyObject* result = PyList_New(array->count);
    if (result == NULL) {
        return NULL;  // 메모리 할당 실패
    }
    
    for (size_t i = 0; i < array->count; i++) {
        PyObject* file_dict = PyDict_New();
        if (file_dict == NULL) {
            Py_DECREF(result);
            return NULL;
        }
        
        // 안전하게 문자열 변환
        if (array->files[i].path) {
            PyObject* path_obj = PyUnicode_FromWideChar(array->files[i].path, -1);
            PyDict_SetItemString(file_dict, "path", path_obj);
            Py_XDECREF(path_obj);
        } else {
            PyDict_SetItemString(file_dict, "path", PyUnicode_FromString(""));
        }
        
        if (array->files[i].name) {
            PyObject* name_obj = PyUnicode_FromWideChar(array->files[i].name, -1);
            PyDict_SetItemString(file_dict, "name", name_obj);
            Py_XDECREF(name_obj);
        } else {
            PyDict_SetItemString(file_dict, "name", PyUnicode_FromString(""));
        }
        
        if (array->files[i].extension) {
            PyObject* ext_obj = PyUnicode_FromWideChar(array->files[i].extension, -1);
            PyDict_SetItemString(file_dict, "extension", ext_obj);
            Py_XDECREF(ext_obj);
        } else {
            PyDict_SetItemString(file_dict, "extension", PyUnicode_FromString(""));
        }
        
        PyDict_SetItemString(file_dict, "size", PyLong_FromLongLong(array->files[i].size));
        PyDict_SetItemString(file_dict, "modified_time", PyLong_FromLongLong(array->files[i].modified_time));
        
        PyList_SetItem(result, i, file_dict);
    }
    
    return result;
}

// scan_usn_journal Python 함수
static PyObject* py_scan_usn_journal(PyObject* self, PyObject* args) {
    PyObject* volume_path_obj;
    wchar_t* volume_path = NULL;
    Py_ssize_t length;
    
    // PyArg_ParseTuple에서 "U"는 PyUnicodeObject*를 받음
    if (!PyArg_ParseTuple(args, "U", &volume_path_obj)) {
        return NULL;
    }
    
    // PyUnicode_AsWideCharString 사용 (메모리 안전)
    volume_path = PyUnicode_AsWideCharString(volume_path_obj, &length);
    if (volume_path == NULL) {
        PyErr_SetString(PyExc_ValueError, "Failed to convert volume path to wide string");
        return NULL;
    }
    
    // USN Journal 스캔
    // GetLastError()를 보존하기 위해 SetLastError(0)으로 초기화
    SetLastError(0);
    FileInfoArray* array = scan_usn_journal(volume_path, NULL);
    
    // volume_path 메모리 해제
    PyMem_Free(volume_path);
    
    if (array == NULL) {
        // Windows 오류 코드 가져오기 (C++ 함수에서 보존된 오류)
        DWORD error = GetLastError();
        char error_msg[512];
        
        // 오류 코드가 없으면 일반 오류로 처리
        if (error == 0) {
            PyErr_SetString(PyExc_RuntimeError, 
                "Failed to scan USN Journal: Unknown error. "
                "Please run as Administrator or check USN Journal permissions.");
        } else if (error == ERROR_ACCESS_DENIED || error == 5) {
            snprintf(error_msg, sizeof(error_msg), 
                "Failed to scan USN Journal: Access denied (error %lu). "
                "Please run as Administrator or check USN Journal permissions.", error);
            PyErr_SetString(PyExc_RuntimeError, error_msg);
        } else if (error == ERROR_FILE_NOT_FOUND || error == 2) {
            snprintf(error_msg, sizeof(error_msg),
                "Failed to scan USN Journal: Volume not found (error %lu). "
                "Check if the drive exists.", error);
            PyErr_SetString(PyExc_RuntimeError, error_msg);
        } else if (error == ERROR_INVALID_PARAMETER || error == 87) {
            snprintf(error_msg, sizeof(error_msg),
                "Failed to scan USN Journal: Invalid parameter (error %lu). "
                "USN Journal may not be enabled on this volume.", error);
            PyErr_SetString(PyExc_RuntimeError, error_msg);
        } else {
            snprintf(error_msg, sizeof(error_msg),
                "Failed to scan USN Journal: Windows error code %lu. "
                "Check if USN Journal is enabled and you have Administrator privileges.", error);
            PyErr_SetString(PyExc_RuntimeError, error_msg);
        }
        return NULL;
    }
    
    // Python 리스트로 변환
    PyObject* result = file_info_array_to_list(array);
    
    // 메모리 해제
    free_file_info_array(array);
    
    return result;
}

// 모듈 메서드 정의
static PyMethodDef usn_scanner_methods[] = {
    {
        "scan_usn_journal",
        py_scan_usn_journal,
        METH_VARARGS,
        "Scan USN Journal for a volume and return file list"
    },
    {NULL, NULL, 0, NULL}
};

// 모듈 정의
static struct PyModuleDef usn_scanner_module = {
    PyModuleDef_HEAD_INIT,
    "usn_scanner_native",
    "Native USN Journal scanner for high-performance file indexing",
    -1,
    usn_scanner_methods
};

// 모듈 초기화
PyMODINIT_FUNC PyInit_usn_scanner_native(void) {
    return PyModule_Create(&usn_scanner_module);
}

