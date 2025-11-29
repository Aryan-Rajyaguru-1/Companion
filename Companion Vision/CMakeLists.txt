# The following lines of boilerplate have to be in your project's
# CMakeLists.txt to compile with ESP-IDF
cmake_minimum_required(VERSION 3.16)

# Set the components to include the tests for.
set(TEST_COMPONENTS "main" CACHE STRING "List of components to test")

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(smart_glasses_ocr)
