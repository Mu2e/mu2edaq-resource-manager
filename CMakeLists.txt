cmake_minimum_required(VERSION 3.14)
project(mu2edaq-resource-manager VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# ── Dependencies ─────────────────────────────────────────────────────────────

# libcurl (system)
find_package(CURL REQUIRED)

# nlohmann/json (fetched automatically)
include(FetchContent)
FetchContent_Declare(
    nlohmann_json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG        v3.11.3
    GIT_SHALLOW    TRUE
)
FetchContent_MakeAvailable(nlohmann_json)

# ── Client library ───────────────────────────────────────────────────────────

add_library(rmclient STATIC
    src/ResourceManagerClient.cpp
)
target_include_directories(rmclient PUBLIC include)
target_link_libraries(rmclient
    PUBLIC
        CURL::libcurl
        nlohmann_json::nlohmann_json
)
target_compile_options(rmclient PRIVATE -Wall -Wextra)

# ── rm-cli ───────────────────────────────────────────────────────────────────

add_executable(rm-cli src/cli/main.cpp)
target_link_libraries(rm-cli PRIVATE rmclient)
target_compile_options(rm-cli PRIVATE -Wall -Wextra)

# ── rm-demo ──────────────────────────────────────────────────────────────────

add_executable(rm-demo src/demo/demo_client.cpp)
target_link_libraries(rm-demo PRIVATE rmclient)
target_compile_options(rm-demo PRIVATE -Wall -Wextra)

# ── Install ──────────────────────────────────────────────────────────────────

include(GNUInstallDirs)
install(TARGETS rm-cli rm-demo DESTINATION ${CMAKE_INSTALL_BINDIR})
install(TARGETS rmclient       DESTINATION ${CMAKE_INSTALL_LIBDIR})
install(DIRECTORY include/     DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})

# ── Summary ──────────────────────────────────────────────────────────────────

message(STATUS "")
message(STATUS "mu2edaq-resource-manager ${PROJECT_VERSION}")
message(STATUS "  CURL:    ${CURL_VERSION_STRING}")
message(STATUS "  Install: ${CMAKE_INSTALL_PREFIX}")
message(STATUS "  Targets: rm-cli  rm-demo  rmclient (static)")
message(STATUS "")
