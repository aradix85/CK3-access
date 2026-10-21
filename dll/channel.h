// channel.h - what the two halves of the DLL share: the reply, the reading of a command, the one
// cast from a number to a pointer, and the input commands (input.cpp) the dispatcher calls.
#pragma once
#include <windows.h>

void emit(const char* format, ...);
bool all_read(const char* p);
bool take(const char** p, char kind, unsigned long long* out);

// The one place a number becomes a pointer. Reading memory at an address that is handed over - by
// Python, by a child list in the game, by Windows - is what this DLL is for, so the cast is the job
// itself and cannot go; this is the single exception to the check that warns about it.
template <typename Pointer, typename Whole>
Pointer as_pointer(Whole number)
{
    return reinterpret_cast<Pointer>(number);   // NOLINT(performance-no-int-to-ptr): see above
}

void keys_enable(bool enable);
void cmd_waitkey(DWORD timeout);
void cmd_swallow(const char* rest);
void cmd_mouse(unsigned x, unsigned y);
void cmd_sendkey(unsigned code);
void cmd_sendchar(unsigned ch);
void cmd_count(void);
void cmd_combo(const char* rest);
