#include "mlx/distributed/utils.h"
#include <windows.h>
#include <iostream>
#include <stdexcept>
#include <utility>

using namespace mlx::core::distributed::detail;

DWORD handles() {
  DWORD count = 0;
  if (!GetProcessHandleCount(GetCurrentProcess(), &count)) {
    throw std::runtime_error("GetProcessHandleCount failed");
  }
  return count;
}

int run(int argc) {
  auto address = parse_address("127.0.0.1", "0");
  // Port zero is invalid for connect and fails without a peer or network wait.
  TCPSocket blocker("ownership-test");
  // Warm up Winsock and exception machinery before counting handles.
  try { TCPSocket::connect("ownership-test", address); }
  catch (const std::runtime_error&) {}
  DWORD before = handles();
  for (int iteration = 0; iteration < 16; ++iteration) {
    int expected_error = 0;
    try {
      TCPSocket::connect("ownership-test", address, 3, 0,
                        [&expected_error](int, int) {
                          expected_error = last_socket_error();
                        });
      return 3;
    } catch (const std::runtime_error& error) {
      if (expected_error == 0 || std::string(error.what()).find(
              "(error: " + std::to_string(expected_error) + ")") ==
              std::string::npos) {
        std::cerr << "Original connect error lost: " << error.what() << '\n';
        return 4;
      }
    }
    try {
      TCPSocket::connect("ownership-test", address, 3, 0,
                        [](int, int) { throw std::runtime_error("callback"); });
      return 3;
    } catch (const std::runtime_error&) {}
    TCPSocket first("ownership-test"), second("ownership-test");
    first = std::move(second);
    first = std::move(first);
  }
  for (int iteration = 0; argc > 1 && iteration < 16; ++iteration) {
    auto listening_address = parse_address("127.0.0.1", "0");
    TCPSocket listener("ownership-test");
    listener.listen("ownership-test", listening_address);
    if (getsockname(listener,
                    reinterpret_cast<sockaddr*>(&listening_address.addr),
                    &listening_address.len) != 0) {
      return 2;
    }
    auto client = TCPSocket::connect("ownership-test", listening_address);
    auto peer = listener.accept("ownership-test");
    const char sent = 'x';
    char received = 0;
    client.send("ownership-test", &sent, 1);
    peer.recv("ownership-test", &received, 1);
    if (received != sent) { return 5; }
  }
  DWORD after = handles();
  std::cout << "handles_before=" << before << " handles_after=" << after << '\n';
  if (before != after) { return 1; }
  try {
    TCPSocket::connect("ownership-test", address, 0, 0);
    return 6;
  } catch (const std::invalid_argument&) {}
  return 0;
}

int main(int argc, char**) {
  try { return run(argc); }
  catch (const std::exception& error) {
    std::cerr << "TCP ownership test failed: " << error.what() << '\n';
    return 2;
  }
}
