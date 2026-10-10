cmake_minimum_required(VERSION 2.8 FATAL_ERROR)

project(keypoints)
find_package(PCL 1.8 REQUIRED)


set (CMAKE_CXX_STANDARD 14)



include_directories(${PCL_INCLUDE_DIRS})
link_directories(${PCL_LIBRARY_DIRS})
add_definitions(${PCL_DEFINITIONS})

set(HEADERS ./include/ )

add_executable (${PROJECT_NAME} keypoints_algorithms.cpp ${HEADERS})
target_link_libraries (${PROJECT_NAME} ${PCL_LIBRARIES})

