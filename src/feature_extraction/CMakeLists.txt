cmake_minimum_required(VERSION 3.10 FATAL_ERROR)

# PCL/VTK may expose the VTK::mpi target, which requires MPI::MPI_C on
# Ubuntu 26.04. Enable C in addition to C++ so CMake can create that target.
project(feature_extraction LANGUAGES C CXX)

find_package(PCL 1.8 REQUIRED COMPONENTS common io search features)

add_executable(feature_extraction feature_extraction.cpp)
target_compile_features(feature_extraction PRIVATE cxx_std_14)
target_include_directories(feature_extraction PRIVATE ${PCL_INCLUDE_DIRS})
target_link_directories(feature_extraction PRIVATE ${PCL_LIBRARY_DIRS})
add_definitions(${PCL_DEFINITIONS})
target_link_libraries(feature_extraction PRIVATE ${PCL_LIBRARIES})
