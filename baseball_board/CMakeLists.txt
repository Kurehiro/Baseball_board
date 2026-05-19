cmake_minimum_required(VERSION 3.8)
project(baseball_board)

find_package(ament_cmake REQUIRED)
find_package(rclpy REQUIRED)
find_package(std_msgs REQUIRED)
find_package(action_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "action/BaseballJudge.action"
  "action/RunnerSend.action"
  DEPENDENCIES action_msgs
)

install(PROGRAMS
  baseball_board/Baseball_field.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME Baseball_field
)

install(PROGRAMS
  baseball_board/pitcher_client.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME pitcher_client
)

install(PROGRAMS
  baseball_board/batter_client.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME batter_client
)

install(PROGRAMS
  baseball_board/runner_server.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME runner_server
)

ament_export_dependencies(rosidl_default_runtime)

ament_package()