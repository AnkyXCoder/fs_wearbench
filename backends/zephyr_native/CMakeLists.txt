cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(wear_bench)

set(WEAR_RECORD_SIZE 128 CACHE STRING "Record size in bytes")
set(WEAR_RECORD_COUNT 1000 CACHE STRING "Number of records to write")
set(WEAR_BACKEND "NVS" CACHE STRING "Backend to use: NVS, ZMS, LITTLEFS")

if(WEAR_BACKEND STREQUAL "NVS")
    set(WEAR_BACKEND_NVS 1)
    set(WEAR_BACKEND_ZMS 0)
    set(WEAR_BACKEND_LITTLEFS 0)
elseif(WEAR_BACKEND STREQUAL "ZMS")
    set(WEAR_BACKEND_NVS 0)
    set(WEAR_BACKEND_ZMS 1)
    set(WEAR_BACKEND_LITTLEFS 0)
elseif(WEAR_BACKEND STREQUAL "LITTLEFS")
    set(WEAR_BACKEND_NVS 0)
    set(WEAR_BACKEND_ZMS 0)
    set(WEAR_BACKEND_LITTLEFS 1)
else()
    message(FATAL_ERROR "Unknown WEAR_BACKEND: ${WEAR_BACKEND}")
endif()

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/src/workload.h.in
    ${CMAKE_CURRENT_BINARY_DIR}/workload.h
    @ONLY
)

target_include_directories(app PRIVATE ${CMAKE_CURRENT_BINARY_DIR})
target_sources(app PRIVATE src/main.c)
