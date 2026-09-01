cmake_minimum_required(VERSION 3.8)
project(bt_direction_stable)

# THE LIBRARY NAME IS THE PLUGIN NAME. bt_navigator loads BT plugins with
# BT::SharedLibrary, which is a plain dlopen of lib<name>.so off the
# LOADER path - not pluginlib, not the ament index. So the name written
# in nav2.yaml's plugin_lib_names is this target, and config.yaml
# (bt_direction.library) is where both readers get it from.
set(PLUGIN_LIB m5v3_direction_stable_bt_node)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

find_package(ament_cmake REQUIRED)
find_package(behaviortree_cpp REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(rclcpp REQUIRED)

add_library(${PLUGIN_LIB} SHARED src/direction_stable_path.cpp)
# BT_PLUGIN_EXPORT IS NOT OPTIONAL AND ITS ABSENCE IS SILENT. Without it
# BT.CPP's BTCPP_EXPORT expands to `static`, BT_REGISTER_NODES compiles
# to a file-local function, the library builds and links clean, and
# `dlsym(handle, "BT_RegisterNodesFromPlugin")` then finds nothing -
# which bt_navigator reports as a plugin that does not register any node.
# Measured here first: the install script's loader probe caught exactly
# that before the rig did.
target_compile_definitions(${PLUGIN_LIB} PRIVATE BT_PLUGIN_EXPORT)
target_compile_options(${PLUGIN_LIB} PRIVATE -Wall -Wextra -Wpedantic)
ament_target_dependencies(${PLUGIN_LIB} behaviortree_cpp nav_msgs rclcpp)

# DESTINATION lib AND NOT lib/${PROJECT_NAME}, because the loader path is
# what finds this file and m5v3.sh puts <install>/lib on it.
install(TARGETS ${PLUGIN_LIB} DESTINATION lib)

ament_package()
