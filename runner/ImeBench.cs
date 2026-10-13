// Types romaji into a text box through a chosen TSF input method (activated
// for this process only), converts with Space, commits with Enter, and
// writes what the text box got.
//
//   ImeBench.exe <clsid> <profile-guid> <keys.tsv> <out.tsv> [limit] [delayMs]
//
// keys.tsv: source, id, keys, expected...   out.tsv: source, id, output
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;

static class Native {
    [StructLayout(LayoutKind.Sequential)]
    public struct INPUT { public uint type; public KEYBDINPUT ki; public ulong pad; }
    [StructLayout(LayoutKind.Sequential)]
    public struct KEYBDINPUT { public ushort wVk; public ushort wScan; public uint dwFlags; public uint time; public IntPtr dwExtraInfo; }
    [DllImport("user32.dll", SetLastError = true)] public static extern uint SendInput(uint n, INPUT[] inputs, int size);
    [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint code, uint type);
    [DllImport("user32.dll")] public static extern short VkKeyScan(char ch);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr pid);
    [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool attach);
    [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
    [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();

    // Windows lets only the window that got the last input take the front;
    // sharing input with the front window's thread lets the bench back in
    // after the person has used another window.
    public static void TakeFront(IntPtr h) {
        if (GetForegroundWindow() == h) return;
        uint front = GetWindowThreadProcessId(GetForegroundWindow(), IntPtr.Zero), me = GetCurrentThreadId();
        bool attached = front != 0 && front != me && AttachThreadInput(me, front, true);
        BringWindowToTop(h);
        SetForegroundWindow(h);
        if (attached) AttachThreadInput(me, front, false);
    }
    [DllImport("imm32.dll")] public static extern IntPtr ImmGetContext(IntPtr h);
    [DllImport("imm32.dll")] public static extern bool ImmReleaseContext(IntPtr h, IntPtr c);
    [DllImport("imm32.dll")] public static extern bool ImmSetOpenStatus(IntPtr c, bool open);
    [DllImport("imm32.dll")] public static extern bool ImmSetConversionStatus(IntPtr c, int conv, int sent);
}

// The person at the PC: a mouse move, click or key that no program sent pauses
// the measurement, which goes on once mouse and keys have been still for IdleMs.
// The hooks run on their own thread so a busy bench never delays the mouse.
static class UserInput {
    public const int IdleMs = 5000;
    delegate IntPtr HookProc(int code, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern IntPtr SetWindowsHookEx(int id, HookProc proc, IntPtr module, uint thread);
    [DllImport("user32.dll")] static extern IntPtr CallNextHookEx(IntPtr hook, int code, IntPtr w, IntPtr l);
    [DllImport("kernel32.dll")] static extern IntPtr GetModuleHandle(string name);
    static HookProc mouseProc, keyProc;   // kept so the collector leaves them alone
    static long lastTicks;
    static int count;

    // How many times the person has touched the PC since the start.
    public static int Count { get { return Thread.VolatileRead(ref count); } }
    public static bool Busy { get { return IdleLeftMs > 0; } }
    public static int IdleLeftMs { get { return Math.Max(0, IdleMs - (int)((DateTime.UtcNow.Ticks - Interlocked.Read(ref lastTicks)) / 10000)); } }

    static void Touch() { Interlocked.Exchange(ref lastTicks, DateTime.UtcNow.Ticks); Interlocked.Increment(ref count); }

    public static void Start() {
        var t = new Thread(() => {
            IntPtr module = GetModuleHandle(null);
            IntPtr mouse = IntPtr.Zero, keys = IntPtr.Zero;
            // Injected events (flag bit 0 for the mouse, 0x10 for keys) are the bench's own keys.
            mouseProc = (c, w, l) => { if (c >= 0 && (Marshal.ReadInt32(l, 12) & 1) == 0) Touch(); return CallNextHookEx(mouse, c, w, l); };
            keyProc = (c, w, l) => { if (c >= 0 && (Marshal.ReadInt32(l, 8) & 0x10) == 0) Touch(); return CallNextHookEx(keys, c, w, l); };
            mouse = SetWindowsHookEx(14, mouseProc, module, 0);   // WH_MOUSE_LL
            keys = SetWindowsHookEx(13, keyProc, module, 0);      // WH_KEYBOARD_LL
            Application.Run();
        });
        t.IsBackground = true;
        t.Start();
    }
}

[ComImport, Guid("71c6e74c-0f28-11d8-a82a-00065b84435c"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface ITfInputProcessorProfileMgr {
    [PreserveSig] int ActivateProfile(uint dwProfileType, ushort langid, ref Guid clsid, ref Guid guidProfile, IntPtr hkl, uint dwFlags);
    [PreserveSig] int DeactivateProfile(uint a, ushort b, ref Guid c, ref Guid d, IntPtr e, uint f);
    [PreserveSig] int GetProfile(uint a, ushort b, ref Guid c, ref Guid d, IntPtr e, IntPtr f);
    [PreserveSig] int EnumProfiles(ushort a, out IntPtr b);
    [PreserveSig] int ReleaseInputProcessor(ref Guid a, uint b);
    [PreserveSig] int RegisterProfile(ref Guid a, ushort b, ref Guid c, IntPtr d, uint e, IntPtr f, uint g, uint h, IntPtr i, uint j, int k, uint l);
    [PreserveSig] int UnregisterProfile(ref Guid a, ushort b, ref Guid c, uint d);
    [PreserveSig] int GetActiveProfile(ref Guid catid, out TF_INPUTPROCESSORPROFILE profile);
}

[StructLayout(LayoutKind.Sequential)]
struct TF_INPUTPROCESSORPROFILE {
    public uint dwProfileType; public ushort langid; public Guid clsid; public Guid guidProfile; public Guid catid;
    public IntPtr hklSubstitute; public uint dwCaps; public IntPtr hkl; public uint dwFlags;
}

class Bench : Form {
    readonly TextBoxBase box = Environment.GetEnvironmentVariable("IMEBENCH_RICH") == "1" ? (TextBoxBase)new RichTextBox() : new TextBox();
    readonly string[] args;
    readonly ProgressBar bar = new ProgressBar { Dock = DockStyle.Bottom, Height = 18 };
    readonly Label status = new Label { Dock = DockStyle.Bottom, Height = 28, Font = new System.Drawing.Font("Yu Gothic UI", 11) };
    static readonly bool ja = System.Globalization.CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "ja";
    // Progress over the whole batch (realime.ps1): a label, the rows done before
    // this set, and the rows of the batch. Without them, this set alone.
    readonly string label = Environment.GetEnvironmentVariable("IMEBENCH_LABEL") ?? "";
    int before, total;
    double typedSeconds;   // time spent typing, pauses left out, for the time left

    public Bench(string[] a) {
        args = a;
        Text = "IME bench"; Width = 1000; Height = 250; TopMost = true;
        box.Multiline = true; box.Dock = DockStyle.Fill; box.Font = new System.Drawing.Font("Yu Gothic UI", 16);
        Controls.Add(box);
        Controls.Add(status);
        Controls.Add(bar);
        Shown += (s, e) => { BeginInvoke(new Action(Run)); };
    }

    void Show(int n, int rows) {
        int done = before + n, all = Math.Max(total, before + rows);
        bar.Maximum = Math.Max(1, all); bar.Value = Math.Min(bar.Maximum, done);
        string left = "";
        if (n > 0) {
            var t = TimeSpan.FromSeconds(typedSeconds / n * (all - done));
            left = ja ? string.Format("　残り約 {0} 分", Math.Ceiling(t.TotalMinutes)) : string.Format(", about {0} min left", Math.Ceiling(t.TotalMinutes));
        }
        status.Text = (label == "" ? "" : label + "　") + (ja ? string.Format("{0} / {1} 文（残り {2} 文）", done, all, all - done) : string.Format("{0} / {1} rows ({2} left)", done, all, all - done)) + left;
    }

    // While the person uses the PC: wait until mouse and keys have been still.
    void WaitIdle() {
        if (!UserInput.Busy) return;
        string was = status.Text;
        while (UserInput.Busy) {
            int s = (UserInput.IdleLeftMs + 999) / 1000;
            status.Text = ja ? string.Format("一時停止中：マウスとキーが止まって {0} 秒後に再開します", s) : string.Format("Paused: goes on {0} s after the mouse and keys stop", s);
            Settle(200);
        }
        status.Text = was;
    }

    internal static void Key(ushort vk, bool up) {
        var i = new Native.INPUT[1];
        i[0].type = 1;
        i[0].ki.wVk = vk;
        i[0].ki.wScan = (ushort)Native.MapVirtualKey(vk, 0);
        i[0].ki.dwFlags = up ? 2u : 0u;
        Native.SendInput(1, i, Marshal.SizeOf(typeof(Native.INPUT)));
    }

    internal static void Press(ushort vk, bool shift) {
        if (shift) Key(0x10, false);
        Key(vk, false); Key(vk, true);
        if (shift) Key(0x10, true);
    }

    internal static void Type(char ch) {
        short scan = Native.VkKeyScan(ch);
        if (scan == -1) return;
        Press((ushort)(scan & 0xFF), (scan & 0x100) != 0);
    }

    internal static void Settle(int ms) {
        var end = DateTime.Now.AddMilliseconds(ms);
        while (DateTime.Now < end) { Application.DoEvents(); Thread.Sleep(10); }
    }

    void OpenJapanese() {
        // IMEBENCH_KEYS: virtual keys (hex, comma-separated) that put the input method in Japanese.
        var keys = Environment.GetEnvironmentVariable("IMEBENCH_KEYS");
        if (!string.IsNullOrEmpty(keys)) {
            foreach (var k in keys.Split(new[] { (char)44 })) { Press(Convert.ToUInt16(k, 16), false); Settle(80); }
            return;
        }
        if (Environment.GetEnvironmentVariable("IMEBENCH_IME_ON") == "1") { Press(0x16, false); return; }
        IntPtr c = Native.ImmGetContext(box.Handle);
        Native.ImmSetOpenStatus(c, true);
        Native.ImmSetConversionStatus(c, 0x0001 | 0x0008, 0);  // native, full shape (hiragana)
        Native.ImmReleaseContext(box.Handle, c);
    }

    void Run() {
        Guid clsid = new Guid(args[0]), profile = new Guid(args[1]);
        int limit = args.Length > 4 ? int.Parse(args[4]) : int.MaxValue;
        int delay = args.Length > 5 ? int.Parse(args[5]) : 150;
        var mgr = (ITfInputProcessorProfileMgr)Activator.CreateInstance(System.Type.GetTypeFromCLSID(new Guid("33C53A50-F456-4884-B049-85FD643ECFED")));
        Native.SetForegroundWindow(Handle);
        box.Focus();
        ushort lang = Environment.GetEnvironmentVariable("IMEBENCH_LANG") == "0409" ? (ushort)0x0409 : (ushort)0x0411;
        int hr = mgr.ActivateProfile(1, lang, ref clsid, ref profile, IntPtr.Zero, 0x10000000);
        Console.WriteLine("activate hr=0x" + hr.ToString("X8"));
        Settle(800);
        Guid keyboard = new Guid("34745C63-B2F0-4784-8B67-5E12C8701A31");
        TF_INPUTPROCESSORPROFILE active;
        mgr.GetActiveProfile(ref keyboard, out active);
        Console.WriteLine("active " + active.clsid + " " + active.guidProfile);
        if (active.clsid != clsid) { Console.WriteLine("not the input method asked for"); Close(); return; }
        OpenJapanese();
        Settle(300);
        var output = new StreamWriter(args[3], false, new UTF8Encoding(false));
        // IMEBENCH_CONTEXT: a file of id, tab, the text before the input (left
        // context, as in AJIMEE-Bench); it is put in the box before typing
        // and taken off what the box holds afterwards.
        var contexts = new Dictionary<string, string>();
        var contextFile = Environment.GetEnvironmentVariable("IMEBENCH_CONTEXT");
        if (!string.IsNullOrEmpty(contextFile)) {
            foreach (var l in File.ReadLines(contextFile, Encoding.UTF8)) {
                int tab = l.IndexOf('\t');
                if (tab > 0) contexts[l.Substring(0, tab)] = l.Substring(tab + 1);
            }
        }
        int n = 0;
        int rows = 0;
        foreach (var l in File.ReadLines(args[2], Encoding.UTF8)) if (l.Split('\t').Length >= 4) rows++;
        rows = Math.Min(rows, limit);
        int.TryParse(Environment.GetEnvironmentVariable("IMEBENCH_BEFORE"), out before);
        int.TryParse(Environment.GetEnvironmentVariable("IMEBENCH_TOTAL"), out total);
        Show(0, rows);
        // Warm-up: input methods that load their data on first use (TEKITO's
        // English) get it loaded before anything is measured.
        if (Environment.GetEnvironmentVariable("IMEBENCH_WARMUP") == "1") {
            WaitForFront();
            box.Focus();
            OpenJapanese();
            foreach (char ch in "korewo github ni push suru") { Type(ch); Settle(30); }
            Press(0x20, false); Settle(500); Press(0x0D, false);
            Settle(4000);
            box.Clear();
        }
        foreach (var line in File.ReadLines(args[2], Encoding.UTF8)) {
            if (n >= limit) break;
            var f = line.Split('\t');
            if (f.Length < 4) continue;
            n++;
            string text = null;
            // Keys go only to this window, and only while nobody else uses the PC:
            // wait for both, and type the sentence again if either changed on the way.
            for (int attempt = 0; text == null && attempt < 5; attempt++) {
                WaitIdle();
                WaitForFront();
                int touches = UserInput.Count;
                var rowStart = DateTime.UtcNow;
                box.Clear();
                string context;
                if (contexts.TryGetValue(f[1], out context) && context.Length > 0) {
                    box.Text = context;
                    box.SelectionStart = box.TextLength;
                } else context = "";
                box.Focus();
                // Some input methods toggle on a mode key (TEKITO's No-convert): those keys once.
                if (n == 1 || Environment.GetEnvironmentVariable("IMEBENCH_KEYS_ONCE") != "1") OpenJapanese();
                // The first row waits longer: an input method may still be switching modes.
                Settle(n == 1 && attempt == 0 ? 1000 : 50);
                Func<bool> undisturbed = () => InFront() && UserInput.Count == touches;
                bool lost = false;
                foreach (char ch in f[2]) {
                    if (!undisturbed()) { lost = true; break; }
                    Type(ch);
                    Settle(delay / 10);
                }
                if (!lost) {
                    Settle(delay);
                    // English: the text as typed (and corrected as typed); nothing to convert.
                    bool english = Environment.GetEnvironmentVariable("IMEBENCH_ENGLISH") == "1";
                    // Live: the conversion is shown while typing; Enter takes it.
                    bool live = Environment.GetEnvironmentVariable("IMEBENCH_LIVE") == "1";
                    if (!english && undisturbed()) {
                        if (!live) Press(Environment.GetEnvironmentVariable("IMEBENCH_CONVERT_KEY") == "1" ? (ushort)0x1C : (ushort)0x20, false);   // Space (or the convert key): convert
                        Settle(delay * 2);
                        if (undisturbed()) Press(0x0D, false);   // Enter: commit
                    }
                    Settle(delay * 2);
                    lost = !undisturbed();
                }
                if (lost) {
                    // Drop what is half typed, in this window only.
                    if (InFront()) Press(0x1B, false);
                    // A person using the PC does not use up a try.
                    if (UserInput.Count != touches) attempt--;
                    continue;
                }
                typedSeconds += (DateTime.UtcNow - rowStart).TotalSeconds;
                text = box.Text.Replace("\r", "").Replace("\n", "");
                if (context.Length > 0 && text.StartsWith(context)) text = text.Substring(context.Length);
            }
            if (text == null) text = "\u0000lost";
            output.WriteLine(f[0] + "\t" + f[1] + "\t" + text);
            output.Flush();
            Show(n, rows);
            if (n % 50 == 0) Console.WriteLine(n + " done");
        }
        output.Close();
        Close();
    }

    bool InFront() { return Native.GetForegroundWindow() == Handle; }

    void WaitForFront() {
        bool told = false;
        while (!InFront()) {
            WaitIdle();
            Native.TakeFront(Handle);
            Settle(300);
            if (!InFront() && !told) { Console.WriteLine("waiting for the bench window to be in front"); told = true; }
        }
    }

    [STAThread]
    static void Main(string[] a) {
        Application.EnableVisualStyles();
        UserInput.Start();
        // With arguments: the batch run (realime.ps1). Without: the window
        // where a person picks the input method and starts a measurement.
        if (a.Length >= 4 && !a[0].StartsWith("--")) Application.Run(new Bench(a));
        else Application.Run(new App());
    }
}
