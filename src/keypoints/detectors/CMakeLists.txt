# Compatible with Ubuntu 22.04 (CMake 3.22) and Ubuntu 26.04+ (CMake 4).
cmake_minimum_required(VERSION 3.5...3.25 FATAL_ERROR)

project(keypoints)
find_package(PCL 1.8 REQUIRED)


set (CMAKE_CXX_STANDARD 14)



include_directories(${PCL_INCLUDE_DIRS})
link_directories(${PCL_LIBRARY_DIRS})
add_definitions(${PCL_DEFINITIONS})

set(HEADERS ./include/ )

add_executable (${PROJECT_NAME} keypoints_algorithms.cpp ${HEADERS})
target_link_libraries (${PROJECT_NAME} ${PCL_LIBRARIES})

