cmake_minimum_required(VERSION 3.24)
project(AltRosetta VERSION 0.0.1 LANGUAGES CXX)

if(NOT APPLE OR NOT CMAKE_SYSTEM_PROCESSOR MATCHES "^(arm64|aarch64)$")
  message(FATAL_ERROR "Phase 0 native experiments require Apple Silicon macOS")
endif()
set(CMAKE_OSX_ARCHITECTURES arm64)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Python3 3.11 REQUIRED COMPONENTS Interpreter)
find_program(XCRUN xcrun REQUIRED)
add_executable(jit_probe experiments/jit_probe.cpp)
target_compile_options(jit_probe PRIVATE -Wall -Wextra -Werror)

set(INTEL_FIXTURE "${CMAKE_CURRENT_BINARY_DIR}/return42_x86_64")
add_custom_command(OUTPUT "${INTEL_FIXTURE}"
  COMMAND "${XCRUN}" clang -arch x86_64 -mmacosx-version-min=10.13 -nostdlib -static
          -Wl,-e,_main -Wl,-no_uuid
          "${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/return42_x86_64.s" -o "${INTEL_FIXTURE}"
  DEPENDS tests/fixtures/return42_x86_64.s
  VERBATIM)
add_custom_target(intel_fixture ALL DEPENDS "${INTEL_FIXTURE}")

include(CTest)
if(BUILD_TESTING)
  add_test(NAME inspector_tests
    COMMAND "${Python3_EXECUTABLE}" -m unittest discover -s tests -v)
  set_tests_properties(inspector_tests PROPERTIES WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}")
  add_test(NAME native_jit_and_intel_metadata
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/check_probes.py"
            "$<TARGET_FILE:jit_probe>" "${INTEL_FIXTURE}")
endif()
