"""Measure elapsed time and peak committed memory for a Windows process tree."""
import _winapi
import argparse
import ctypes as ct
from ctypes import wintypes as w
import json
import msvcrt
import os
from pathlib import Path
import subprocess
import time


class BasicLimits(ct.Structure):
    _fields_ = [("process_time", ct.c_int64), ("job_time", ct.c_int64),
                ("flags", w.DWORD), ("min_working_set", ct.c_size_t),
                ("max_working_set", ct.c_size_t), ("active_processes", w.DWORD),
                ("affinity", ct.c_size_t), ("priority", w.DWORD),
                ("scheduling", w.DWORD)]


class JobLimits(ct.Structure):
    _fields_ = [("basic", BasicLimits), ("io", ct.c_uint64 * 6),
                ("process_limit", ct.c_size_t), ("job_limit", ct.c_size_t),
                ("peak_process", ct.c_size_t), ("peak_job", ct.c_size_t)]


def kernel_function(name, result, *args):
    function = getattr(ct.WinDLL("kernel32", use_last_error=True), name)
    function.restype = result
    function.argtypes = args
    return function


def check(success):
    if not success:
        raise ct.WinError(ct.get_last_error())


def measure(command, output, error):
    create_job = kernel_function("CreateJobObjectW", w.HANDLE, ct.c_void_p, w.LPCWSTR)
    assign = kernel_function("AssignProcessToJobObject", w.BOOL, w.HANDLE, w.HANDLE)
    resume = kernel_function("ResumeThread", w.DWORD, w.HANDLE)
    query = kernel_function("QueryInformationJobObject", w.BOOL, w.HANDLE, ct.c_int,
                            ct.c_void_p, w.DWORD, ct.c_void_p)
    configure = kernel_function("SetInformationJobObject", w.BOOL, w.HANDLE, ct.c_int,
                                ct.c_void_p, w.DWORD)
    job = create_job(None, None)
    check(job)
    process = thread = None
    running = False
    try:
        limits = JobLimits()
        limits.basic.flags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        check(configure(job, 9, ct.byref(limits), ct.sizeof(limits)))
        with open(os.devnull, "rb") as stdin, output.open("wb") as stdout, error.open("wb") as stderr:
            handles = [msvcrt.get_osfhandle(stream.fileno()) for stream in (stdin, stdout, stderr)]
            for handle in handles:
                os.set_handle_inheritable(handle, True)
            startup = subprocess.STARTUPINFO(
                dwFlags=subprocess.STARTF_USESTDHANDLES,
                hStdInput=handles[0], hStdOutput=handles[1], hStdError=handles[2],
                lpAttributeList={"handle_list": handles},
            )
            start = time.perf_counter()
            process, thread, _, _ = _winapi.CreateProcess(
                None, subprocess.list2cmdline(command), None, None, True,
                0x00000004, None, None, startup,  # CREATE_SUSPENDED
            )
            check(assign(job, process))
            check(resume(thread) != 0xFFFFFFFF)
            running = True
            _winapi.WaitForSingleObject(process, _winapi.INFINITE)
            elapsed = time.perf_counter() - start
            limits = JobLimits()
            check(query(job, 9, ct.byref(limits), ct.sizeof(limits), None))
            code = _winapi.GetExitCodeProcess(process)
            if code:
                raise RuntimeError(f"child exited with code {code}; see {error}")
            return {"elapsed_seconds": elapsed, "peak_tree_commit_bytes": limits.peak_job}
    finally:
        if process is not None:
            if not running:
                _winapi.TerminateProcess(process, 1)
            _winapi.CloseHandle(process)
        if thread is not None:
            _winapi.CloseHandle(thread)
        _winapi.CloseHandle(job)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("error", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command:
        parser.error("missing command")
    print(json.dumps(measure(args.command, args.output, args.error)))


if __name__ == "__main__":
    main()
