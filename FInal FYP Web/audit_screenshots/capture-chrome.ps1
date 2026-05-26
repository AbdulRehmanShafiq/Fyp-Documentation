param(
    [Parameter(Mandatory=$true)][string]$OutFile,
    [string]$WindowTitleContains = "vousFin"
)

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

$signature = @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public class Win32 {
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll", CharSet=CharSet.Auto)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc enumProc, IntPtr lParam);

    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    public static extern bool GetClientRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    public static extern bool ClientToScreen(IntPtr hWnd, ref POINT lpPoint);

    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {
        public int Left, Top, Right, Bottom;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct POINT {
        public int X, Y;
    }
}
"@

Add-Type -TypeDefinition $signature -ErrorAction SilentlyContinue

$matchedHwnd = [IntPtr]::Zero
$matchedTitle = ""

$enumProc = [Win32+EnumWindowsProc] {
    param([IntPtr]$hWnd, [IntPtr]$lParam)
    if (-not [Win32]::IsWindowVisible($hWnd)) { return $true }
    $sb = New-Object System.Text.StringBuilder 512
    [Win32]::GetWindowText($hWnd, $sb, 512) | Out-Null
    $title = $sb.ToString()
    if ($title -like "*$WindowTitleContains*") {
        $script:matchedHwnd = $hWnd
        $script:matchedTitle = $title
        return $false
    }
    return $true
}

[Win32]::EnumWindows($enumProc, [IntPtr]::Zero) | Out-Null

if ($matchedHwnd -eq [IntPtr]::Zero) {
    Write-Error "Window not found containing '$WindowTitleContains'"
    exit 1
}

# Bring to foreground
[Win32]::ShowWindow($matchedHwnd, 9) | Out-Null   # SW_RESTORE
[Win32]::SetForegroundWindow($matchedHwnd) | Out-Null
Start-Sleep -Milliseconds 300

# Get client area in screen coords
$clientRect = New-Object Win32+RECT
[Win32]::GetClientRect($matchedHwnd, [ref]$clientRect) | Out-Null
$origin = New-Object Win32+POINT
$origin.X = 0; $origin.Y = 0
[Win32]::ClientToScreen($matchedHwnd, [ref]$origin) | Out-Null

$w = $clientRect.Right - $clientRect.Left
$h = $clientRect.Bottom - $clientRect.Top

if ($w -le 0 -or $h -le 0) {
    Write-Error "Invalid client rect: $w x $h"
    exit 1
}

$bmp = New-Object System.Drawing.Bitmap $w, $h
$gfx = [System.Drawing.Graphics]::FromImage($bmp)
$gfx.CopyFromScreen($origin.X, $origin.Y, 0, 0, $bmp.Size, [System.Drawing.CopyPixelOperation]::SourceCopy)

$dir = Split-Path -Parent $OutFile
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }

$bmp.Save($OutFile, [System.Drawing.Imaging.ImageFormat]::Png)
$gfx.Dispose()
$bmp.Dispose()

Write-Output "Saved $w x $h -> $OutFile (title: $matchedTitle)"
