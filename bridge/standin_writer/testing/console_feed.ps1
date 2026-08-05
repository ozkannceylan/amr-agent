# TEST SCAFFOLDING -- types operator commands into the stand-in writer's
# OWN console, from another process. It is not part of the writer.
#
# WHY IT EXISTS. The writer reads its console per key and non-blocking
# ([Console]::KeyAvailable + [Console]::ReadKey), which is what stops a
# typing operator from stalling the loop and freezing the heartbeat. That
# path only exists when the process owns a real console, so a build check
# that drives it must put real key events into that console's input
# buffer. This script does exactly that and nothing else: it attaches to
# the target process's console and calls WriteConsoleInput.
#
# It does NOT use SendKeys or any focus-dependent input, so it cannot type
# into a window that happens to be in front -- it addresses one console by
# process id.
#
#   .\console_feed.ps1 -TargetPid <pid> -Text 'estop close' -Enter
#   .\console_feed.ps1 -TargetPid <pid> -Text 'status' -PerKeyDelayMs 1000 -Enter

param(
  [Parameter(Mandatory = $true)][int]$TargetPid,
  [Parameter(Mandatory = $true)][string]$Text,
  [switch]$Enter,
  [int]$PerKeyDelayMs = 0
)

$ErrorActionPreference = 'Stop'

if (-not ('AmrConsoleFeed' -as [type])) {
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

// CharSet.Unicode is load-bearing on both structs and on every entry point
// below: the default is Ansi, which marshals System.Char as one byte, and
// that both corrupts the INPUT_RECORD layout and turns "CONIN$" into bytes
// CreateFileW cannot read (observed: ERROR_FILE_NOT_FOUND from a console
// that was demonstrably attached).
[StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
public struct KEY_EVENT_RECORD {
    public int bKeyDown;
    public ushort wRepeatCount;
    public ushort wVirtualKeyCode;
    public ushort wVirtualScanCode;
    public char UnicodeChar;
    public uint dwControlKeyState;
}

[StructLayout(LayoutKind.Explicit, CharSet = CharSet.Unicode)]
public struct INPUT_RECORD {
    [FieldOffset(0)] public ushort EventType;
    [FieldOffset(4)] public KEY_EVENT_RECORD KeyEvent;
}

public static class AmrConsoleFeed {
    const uint GENERIC_READ = 0x80000000, GENERIC_WRITE = 0x40000000;
    const uint FILE_SHARE_READ = 1, FILE_SHARE_WRITE = 2, OPEN_EXISTING = 3;
    const ushort KEY_EVENT = 1;

    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool FreeConsole();
    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool AttachConsole(uint dwProcessId);
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern IntPtr CreateFileW(string name, uint access, uint share, IntPtr sec, uint disp, uint flags, IntPtr templ);
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern bool WriteConsoleInputW(IntPtr h, INPUT_RECORD[] recs, uint len, out uint written);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool CloseHandle(IntPtr h);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern short VkKeyScanW(char ch);

    static INPUT_RECORD Rec(char ch, ushort vk, bool down) {
        INPUT_RECORD r = new INPUT_RECORD();
        r.EventType = KEY_EVENT;
        r.KeyEvent.bKeyDown = down ? 1 : 0;
        r.KeyEvent.wRepeatCount = 1;
        r.KeyEvent.wVirtualKeyCode = vk;
        r.KeyEvent.wVirtualScanCode = 0;
        r.KeyEvent.UnicodeChar = ch;
        r.KeyEvent.dwControlKeyState = 0;
        return r;
    }

    // Sends one character (or VK_RETURN when ch == '\r') into the console
    // this process is currently attached to. Down + up, as a real key.
    public static void SendChar(char ch) {
        ushort vk;
        if (ch == '\r') vk = 0x0D;
        else { short s = VkKeyScanW(ch); vk = (ushort)(s & 0xFF); }
        IntPtr h = CreateFileW("CONIN$", GENERIC_READ | GENERIC_WRITE,
                               FILE_SHARE_READ | FILE_SHARE_WRITE, IntPtr.Zero, OPEN_EXISTING, 0, IntPtr.Zero);
        if (h == (IntPtr)(-1)) throw new Exception("CreateFile CONIN$ failed: " + Marshal.GetLastWin32Error());
        try {
            INPUT_RECORD[] recs = new INPUT_RECORD[] { Rec(ch, vk, true), Rec(ch, vk, false) };
            uint written;
            if (!WriteConsoleInputW(h, recs, (uint)recs.Length, out written))
                throw new Exception("WriteConsoleInput failed: " + Marshal.GetLastWin32Error());
        } finally { CloseHandle(h); }
    }
}
'@
}

[void][AmrConsoleFeed]::FreeConsole()
if (-not [AmrConsoleFeed]::AttachConsole([uint32]$TargetPid)) {
  throw ("AttachConsole({0}) failed: {1}. The target must be running in its own console window." -f $TargetPid, [Runtime.InteropServices.Marshal]::GetLastWin32Error())
}
try {
  foreach ($ch in $Text.ToCharArray()) {
    [AmrConsoleFeed]::SendChar($ch)
    if ($PerKeyDelayMs -gt 0) { Start-Sleep -Milliseconds $PerKeyDelayMs }
  }
  if ($Enter) { [AmrConsoleFeed]::SendChar([char]13) }
} finally {
  [void][AmrConsoleFeed]::FreeConsole()
}
Write-Output ("fed {0} key(s){1} to pid {2}" -f $Text.Length, $(if ($Enter) { ' + Enter' } else { '' }), $TargetPid)
