cmake_minimum_required(VERSION 2.8 FATAL_ERROR)

project(Crop)
find_package(PCL 1.8 REQUIRED)


set (CMAKE_CXX_STANDARD 14)



include_directories(${PCL_INCLUDE_DIRS})
link_directories(${PCL_LIBRARY_DIRS})
add_definitions(${PCL_DEFINITIONS})

add_executable (${PROJECT_NAME} crop.cpp ./include/functions.hpp ./src/functions.cpp)
target_link_libraries (${PROJECT_NAME} ${PCL_LIBRARIES})

add_executable (crop_nine-keypoints crop_nine-keypoints.cpp ./include/functions.hpp ./src/functions.cpp)
target_link_libraries (crop_nine-keypoints ${PCL_LIBRARIES})
