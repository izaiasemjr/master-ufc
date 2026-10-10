cmake_minimum_required(VERSION 3.10 FATAL_ERROR)

project(matching_batch LANGUAGES CXX)

find_package(PCL 1.8 REQUIRED COMPONENTS common io kdtree)

add_executable(matching_batch matching_batch.cpp)
target_compile_features(matching_batch PRIVATE cxx_std_14)
target_include_directories(matching_batch PRIVATE ${PCL_INCLUDE_DIRS})
target_link_directories(matching_batch PRIVATE ${PCL_LIBRARY_DIRS})
add_definitions(${PCL_DEFINITIONS})
target_link_libraries(matching_batch PRIVATE ${PCL_LIBRARIES})
