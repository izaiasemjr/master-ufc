# CMake 4 (Ubuntu 26.04+) no longer supports compatibility below 3.5.
# The range remains compatible with the CMake 3.22 packaged by Ubuntu 22.04.
cmake_minimum_required(VERSION 3.5...3.25 FATAL_ERROR)

project(CP-ICP_ORG)

find_package(PCL 1.0 REQUIRED)

set (CMAKE_CXX_STANDARD 11)
list(REMOVE_ITEM PCL_LIBRARIES "vtkproj4")
include_directories(${PCL_INCLUDE_DIRS})
link_directories(${PCL_LIBRARY_DIRS})
add_definitions(${PCL_DEFINITIONS})

set(SOURCES ./src/izaias_functions.cpp)
set(HEADERS ./include/izaias_functions.hpp)

add_executable (icp-cp main.cpp ${SOURCES} ${HEADERS})
target_link_libraries (icp-cp ${PCL_LIBRARIES})


#set(MAIN example_registro.cpp)
#add_executable (registro example_registro.cpp ${SOURCES} ${HEADERS})
#target_link_libraries (registro ${PCL_LIBRARIES})


#set(MAIN example_quadrantes.cpp)
#add_executable (quadrantes example_quadrantes.cpp ${SOURCES} ${HEADERS})
#target_link_libraries (quadrantes ${PCL_LIBRARIES})


