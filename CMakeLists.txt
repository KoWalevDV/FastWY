cmake_minimum_required(VERSION 3.12)
project(FastWY LANGUAGES CXX)

add_executable(fastwy src/main.cpp src/fastwy.cpp)
set_target_properties(fastwy PROPERTIES CXX_STANDARD 14 CXX_STANDARD_REQUIRED YES CXX_EXTENSIONS NO)

enable_testing()
add_test(NAME toy_exact COMMAND ${CMAKE_COMMAND}
    -DPROGRAM=$<TARGET_FILE:fastwy> -DSOURCE=${CMAKE_CURRENT_SOURCE_DIR}
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/toy.cmake)

find_package(Python3 COMPONENTS Interpreter QUIET)
if(Python3_Interpreter_FOUND)
    add_test(NAME exhaustive_oracle COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/exhaustive_oracle.py $<TARGET_FILE:fastwy>)
    add_test(NAME reference_storage COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_reference_storage.py)
endif()

add_executable(fastwy_core_tests tests/core_tests.cpp)
set_target_properties(fastwy_core_tests PROPERTIES CXX_STANDARD 14 CXX_STANDARD_REQUIRED YES CXX_EXTENSIONS NO)
add_test(NAME core_modules COMMAND fastwy_core_tests)
