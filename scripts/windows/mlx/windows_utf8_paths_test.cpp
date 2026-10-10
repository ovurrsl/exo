// Native validation of the Windows-only header in the reviewed MLX patch.
#include "mlx/windows_utils.h"

#include <cassert>
#include <fcntl.h>
#include <iostream>

int wmain(int argc, wchar_t** argv) {
  assert(argc == 2);
  namespace windows = mlx::core::windows;
  auto root = std::filesystem::path(argv[1]);
  std::filesystem::create_directories(root);
  auto path = root / L"ağırlık 权重 🙂.bin";
  auto utf8 = windows::path_utf8(path);
  assert(windows::utf8_path(utf8) == path);
  for (const std::string invalid : {std::string("\xff", 1),
                                   std::string("\xc0\xaf", 2),
                                   std::string("\xed\xa0\x80", 3)}) {
    bool rejected = false;
    try {
      windows::utf8_to_wide(invalid);
    } catch (const std::invalid_argument&) {
      rejected = true;
    }
    assert(rejected);
  }
  int writer = windows::open_utf8(utf8, O_CREAT | O_WRONLY | O_TRUNC | O_BINARY);
  assert(writer >= 0);
  assert(::_write(writer, "abc", 3) == 3);
  assert(::_close(writer) == 0);
  int reader = windows::open_utf8(utf8, O_RDONLY | O_BINARY);
  assert(reader >= 0);
  char data[3];
  assert(::_read(reader, data, sizeof(data)) == 3);
  assert(std::string(data, sizeof(data)) == "abc");
  assert(::_close(reader) == 0);
  assert(::SetEnvironmentVariableW(L"EXO_UTF8_UNIT_PATH", path.c_str()));
  assert(windows::getenv_utf8(L"EXO_UTF8_UNIT_PATH") == utf8);
  assert(::SetEnvironmentVariableW(L"EXO_UTF8_UNIT_PATH", nullptr));
  assert(!windows::getenv_utf8(L"EXO_UTF8_UNIT_PATH"));
  if (::GetACP() != CP_UTF8) {
    assert(!windows::path_ansi(root / L"模型 🙂"));
  }
  std::cout << "PASS UTF8 roundtrip, invalid sequences, Unicode read/write, wide env\n";
}
