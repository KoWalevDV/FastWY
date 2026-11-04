cmake_minimum_required(VERSION 3.12)
project(FastWY LANGUAGES CXX)

add_executable(fastwy src/main.cpp src/fastwy.cpp)
set_target_properties(fastwy PROPERTIES CXX_STANDARD 14 CXX_STANDARD_REQUIRED YES CXX_EXTENSIONS NO)

enable_testing()
add_test(NAME toy_exact COMMAND ${CMAKE_COMMAND}
    -DPROGRAM=$<TARGET_FILE:fastwy> -DSOURCE=${CMAKE_CURRENT_SOURCE_DIR}
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/toy.cmake)
