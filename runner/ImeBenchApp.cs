// The measuring window: the person picks the input method and its mode in
// the text box the usual way (Win+Space and so on), picks a set, and starts.
// The bench types each row's keys, commits the way the mode needs, records
// the text, and shows how far it is. Nothing on the PC is changed: the input
// method in use is read, not switched.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Windows.Forms;
using Microsoft.Win32;

class App : Form {
    // How a mode commits a row: Space then Enter, Enter alone, or nothing.
    enum Commit { SpaceEnter, Enter, None }
    class Mode {
        public string[] label; public string key; public Commit commit;
        public Mode(string ja, string en, string k, Commit c) { label = new[] { ja, en }; key = k; commit = c; }
    }
    static readonly Mode[] Modes = {
        new Mode("日本語（Space で変換、Enter で確定）", "Japanese (Space converts, Enter commits)", "jp", Commit.SpaceEnter),
        new Mode("日本語（ライブ変換・自動変換、Enter で確定）", "Japanese (live / automatic conversion, Enter commits)", "live", Commit.Enter),
        new Mode("英語まじり（Space で変換、Enter で確定）", "Japanese with English (Space converts, Enter commits)", "mix", Commit.SpaceEnter),
        new Mode("英語まじり（自動変換、Enter で確定）", "Japanese with English (automatic, Enter commits)", "mixlive", Commit.Enter),
        new Mode("英語（自動修正）", "English (autocorrect)", "auto", Commit.None),
        new Mode("Direct（そのまま入力）", "Direct (typed as is)", "direct", Commit.None),
    };
    // UI text, Japanese and English; the language follows Windows at start.
    static readonly Dictionary<string, string[]> T = new Dictionary<string, string[]> {
        { "set", new[] { "セット:", "Set:" } },
        { "name", new[] { "名前:", "Name:" } },
        { "mode", new[] { "モード:", "Mode:" } },
        { "learning", new[] { "学習:", "Learning:" } },
        { "learningHint", new[] { "（IME の設定どおりに選んでください）", "(as set in the input method)" } },
        { "start", new[] { "測定開始", "Start" } },
        { "stop", new[] { "中止", "Stop" } },
        { "all", new[] { "通しで測る", "Measure all" } },
        { "stageJa", new[] { "日本語", "Japanese" } },
        { "stageMix", new[] { "英語まじりの日本語", "Japanese with English" } },
        { "stageEn", new[] { "英語", "English" } },
        { "stagePrompt", new[] { "次は「{0}」を測ります（{1} セット）。\nIME をそのモードにしてから「はい」を押してください。\nこの IME にないモードなら「いいえ」でとばします。",
                                 "Next: {0} ({1} sets).\nPut the input method in that mode, then press Yes.\nPress No to skip a mode this input method does not have." } },
        { "open", new[] { "結果フォルダを開く", "Open results folder" } },
        { "ready", new[] { "入力欄をクリックして、測る IME とモードを選んでから「測定開始」を押してください。",
                           "Click the text box, choose the input method and its mode, then press Start." } },
        { "noSets", new[] { "セットが見つかりません: ", "No sets found: " } },
        { "noIme", new[] { "キーボードのみ（IME なし）", "Keyboard only (no input method)" } },
        { "cannotRead", new[] { "読み取れません: ", "Cannot read: " } },
        { "waitFront", new[] { "測定ウィンドウが前面にないので待っています。クリックして前面に戻してください。",
                               "Waiting: the bench window is not in front. Click it to bring it back." } },
        { "chooseLearning", new[] { "学習が ON か OFF かを選んでください（IME の設定どおりに）。",
                                    "Choose whether learning is on or off (as set in the input method)." } },
        { "probe", new[] { "試し打ち中…", "Trying three rows…" } },
        { "notConverting", new[] { "日本語に変換されていません。IME とモード（ひらがな入力になっているか、IME 本体のアプリが起動しているか）を確かめてください。",
                                   "Nothing is converted to Japanese. Check the input method and its mode (kana input on, and the input method's own app running)." } },
        { "progress", new[] { "{0} / {1} 文（残り {3} 文）　残り約 {2}　（マウスかキーを触ると一時停止します）", "{0} / {1} rows ({3} left), about {2} left (touching the mouse or keys pauses it)" } },
        { "paused", new[] { "一時停止中：マウスとキーが止まって {0} 秒後に再開します", "Paused: goes on {0} s after the mouse and keys stop" } },
        { "minutes", new[] { "{0} 分", "{0} min" } },
        { "seconds", new[] { "{0} 秒", "{0} s" } },
        { "done", new[] { "完了しました: ", "Done: " } },
        { "stopped", new[] { "途中で止まりました（結果は不完全です）: ", "Stopped before the end (incomplete): " } },
    };
    int lang = System.Globalization.CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "ja" ? 0 : 1;
    string L(string key) { return T[key][lang]; }
    const int Delay = 150;   // the same pace as the batch runs

    readonly TextBox box = new TextBox { Multiline = true, Font = new Font("Yu Gothic UI", 16), Height = 70, Dock = DockStyle.Top };
    readonly Label imeLabel = new Label { AutoSize = true };
    readonly ComboBox setBox = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 260 };
    readonly ComboBox modeBox = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 360 };
    readonly RadioButton learnOn = new RadioButton { Text = "ON", AutoSize = true };
    readonly RadioButton learnOff = new RadioButton { Text = "OFF", AutoSize = true };
    readonly TextBox nameBox = new TextBox { Width = 200 };
    readonly Button start = new Button { Width = 120, Height = 34 };
    readonly Button stop = new Button { Width = 80, Height = 34, Enabled = false };
    readonly Button all = new Button { Width = 140, Height = 34 };
    readonly ProgressBar bar = new ProgressBar { Width = 560, Height = 22 };
    readonly Label status = new Label { AutoSize = true };
    readonly Button openFolder = new Button { Width = 180, Visible = false };
    readonly Label labSet = new Label { AutoSize = true }, labName = new Label { AutoSize = true }, labMode = new Label { AutoSize = true },
                   labLearn = new Label { AutoSize = true }, labHint = new Label { AutoSize = true };
    readonly ComboBox langBox = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 100 };
    readonly Timer poll = new Timer { Interval = 1000 };

    readonly string root, setsDir, resultsDir;
    Dictionary<string, string> kinds = new Dictionary<string, string>();
    Guid imeClsid, imeProfile;
    string imeDll = "", imeProduct = "", imeVersion = "";
    bool stopping;
    string lastRun;

    public App() {
        string exeDir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
        // Public repository: runner\ next to sets\ and results\. The private kit: dev\sets, dev\runs.
        bool pub = Path.GetFileName(exeDir).Equals("runner", StringComparison.OrdinalIgnoreCase);
        root = pub ? Path.GetDirectoryName(exeDir) : exeDir;
        setsDir = pub ? Path.Combine(root, "sets") : Path.Combine(root, "dev", "sets");
        resultsDir = pub ? Path.Combine(root, "results") : Path.Combine(root, "dev", "runs");

        Text = "IME精度測定 — IME Benchmark system";
        try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }
        Width = 640; Height = 400; TopMost = true; FormBorderStyle = FormBorderStyle.FixedSingle; MaximizeBox = false;
        var panel = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.TopDown, Padding = new Padding(10), WrapContents = false };
        panel.Controls.Add(Row(langBox, new Label { Text = "IME:", AutoSize = true }, imeLabel));
        panel.Controls.Add(Row(labSet, setBox, labName, nameBox));
        panel.Controls.Add(Row(labMode, modeBox));
        panel.Controls.Add(Row(labLearn, learnOn, learnOff, labHint));
        panel.Controls.Add(Row(start, all, stop, openFolder));
        panel.Controls.Add(bar);
        panel.Controls.Add(status);
        Controls.Add(panel);
        Controls.Add(box);

        langBox.Items.Add("日本語"); langBox.Items.Add("English");
        langBox.SelectedIndex = lang;
        langBox.SelectedIndexChanged += (s, e) => { lang = langBox.SelectedIndex; ApplyLanguage(); };
        ApplyLanguage();
        LoadSets();
        start.Click += (s, e) => Measure();
        all.Click += (s, e) => MeasureAll();
        stop.Click += (s, e) => { stopping = true; };
        openFolder.Click += (s, e) => { if (lastRun != null) Process.Start("explorer.exe", lastRun); };
        poll.Tick += (s, e) => ReadIme();
        poll.Start();
        Shown += (s, e) => { box.Focus(); ReadIme(); Scripted(); };
    }

    // Optional: --set NAME --mode KEY --keys 1A,1C --start, the same steps a
    // person takes (pick the set and mode, put the input method in its mode,
    // press the button), for a scripted run.
    void Scripted() {
        var a = Environment.GetCommandLineArgs();
        string keys = null; bool go = false, goAll = false;
        for (int i = 1; i < a.Length; i++) {
            if (a[i] == "--set" && i + 1 < a.Length) setBox.SelectedItem = a[++i];
            else if (a[i] == "--mode" && i + 1 < a.Length) { string m = a[++i]; for (int j = 0; j < Modes.Length; j++) if (Modes[j].key == m) modeBox.SelectedIndex = j; }
            else if (a[i] == "--keys" && i + 1 < a.Length) keys = a[++i];
            else if (a[i] == "--learning" && i + 1 < a.Length) { string l = a[++i]; learnOn.Checked = l == "on"; learnOff.Checked = l == "off"; }
            else if (a[i] == "--lang" && i + 1 < a.Length) langBox.SelectedIndex = a[++i] == "en" ? 1 : 0;
            else if (a[i] == "--start") go = true;
            else if (a[i] == "--all") { go = true; goAll = true; }
        }
        if (keys != null) {
            Native.SetForegroundWindow(Handle);
            box.Focus();
            Bench.Settle(500);
            foreach (var k in keys.Split(',')) { Bench.Press(Convert.ToUInt16(k, 16), false); Bench.Settle(150); }
            Bench.Settle(500);
            ReadIme();
        }
        if (go) BeginInvoke(new Action(goAll ? (Action)MeasureAll : Measure));
    }

    void ApplyLanguage() {
        int mode = Math.Max(0, modeBox.SelectedIndex);
        modeBox.Items.Clear();
        foreach (var m in Modes) modeBox.Items.Add(m.label[lang]);
        modeBox.SelectedIndex = mode;
        labSet.Text = L("set"); labName.Text = L("name"); labMode.Text = L("mode");
        labLearn.Text = L("learning"); labHint.Text = L("learningHint");
        start.Text = L("start"); all.Text = L("all"); stop.Text = L("stop"); openFolder.Text = L("open");
        if (!stop.Enabled && !openFolder.Visible) status.Text = L("ready");
        if (imeClsid == Guid.Empty && imeProduct != "") { imeProduct = ""; ReadIme(); }
    }

    static FlowLayoutPanel Row(params Control[] controls) {
        var row = new FlowLayoutPanel { AutoSize = true, FlowDirection = FlowDirection.LeftToRight, WrapContents = false, Margin = new Padding(0, 2, 0, 2) };
        foreach (var c in controls) { c.Margin = new Padding(3, 6, 3, 0); row.Controls.Add(c); }
        return row;
    }

    void LoadSets() {
        var json = Path.Combine(setsDir, "sets.json");
        if (!File.Exists(json)) { status.Text = L("noSets") + setsDir; start.Enabled = false; return; }
        foreach (Match m in Regex.Matches(File.ReadAllText(json), "\"([^\"]+)\"\\s*:\\s*\"([^\"]+)\""))
            if (File.Exists(Path.Combine(setsDir, m.Groups[1].Value + ".tsv"))) kinds[m.Groups[1].Value] = m.Groups[2].Value;
        foreach (var k in kinds.Keys.OrderBy(k => k)) setBox.Items.Add(k);
        if (setBox.Items.Count > 0) setBox.SelectedIndex = 0;
    }

    // The input method active for this window, and the DLL its TSF class loads.
    void ReadIme() {
        try {
            var mgr = (ITfInputProcessorProfileMgr)Activator.CreateInstance(Type.GetTypeFromCLSID(new Guid("33C53A50-F456-4884-B049-85FD643ECFED")));
            Guid keyboard = new Guid("34745C63-B2F0-4784-8B67-5E12C8701A31");
            TF_INPUTPROCESSORPROFILE p;
            mgr.GetActiveProfile(ref keyboard, out p);
            if (p.clsid == imeClsid && p.guidProfile == imeProfile && imeProduct != "") return;
            string dll = "", product = "", version = "";
            if (p.clsid != Guid.Empty) {
                dll = Registry.GetValue(@"HKEY_CLASSES_ROOT\CLSID\{" + p.clsid + @"}\InprocServer32", "", "") as string ?? "";
                dll = Environment.ExpandEnvironmentVariables(dll);
                if (File.Exists(dll)) {
                    var v = FileVersionInfo.GetVersionInfo(dll);
                    product = string.IsNullOrEmpty(v.ProductName) ? Path.GetFileNameWithoutExtension(dll) : v.ProductName;
                    version = string.IsNullOrEmpty(v.FileVersion) ? "(" + File.GetLastWriteTime(dll).ToString("yyyy-MM-dd") + ")" : v.FileVersion;
                }
            } else {
                product = L("noIme");
            }
            // The user's folders as variables: a published result does not carry the user name.
            string shown = dll.Replace(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "%LOCALAPPDATA%")
                              .Replace(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "%USERPROFILE%");
            imeClsid = p.clsid; imeProfile = p.guidProfile; imeDll = shown; imeProduct = product; imeVersion = version;
            imeLabel.Text = product + " " + version;
            nameBox.Text = Regex.Replace(product.ToLowerInvariant(), "[^a-z0-9]+", "");
        } catch (Exception e) {
            imeLabel.Text = L("cannotRead") + e.Message;
        }
    }

    bool InFront() { return Native.GetForegroundWindow() == Handle; }

    void WaitForFront() {
        while (!InFront() && !stopping) {
            WaitIdle();
            status.Text = L("waitFront");
            Native.TakeFront(Handle);
            Bench.Settle(300);
        }
    }

    // While the person uses the PC: wait until mouse and keys have been still.
    double pausedSeconds;
    void WaitIdle() {
        if (!UserInput.Busy || stopping) return;
        string was = status.Text;
        var start = DateTime.UtcNow;
        while (UserInput.Busy && !stopping) {
            status.Text = string.Format(L("paused"), (UserInput.IdleLeftMs + 999) / 1000);
            Bench.Settle(200);
        }
        pausedSeconds += (DateTime.UtcNow - start).TotalSeconds;
        status.Text = was;
    }

    // Types one row's keys and returns what the text box got (null: lost the
    // front, or the person used the PC on the way; the row is then typed again).
    bool touched;
    string TypeRow(string keys, Commit commit) {
        touched = false;
        WaitIdle();
        WaitForFront();
        int touches = UserInput.Count;
        Func<bool> undisturbed = () => InFront() && UserInput.Count == touches && !stopping;
        box.Clear();
        box.Focus();
        Bench.Settle(50);
        bool lost = false;
        foreach (char ch in keys) {
            if (!undisturbed()) { lost = true; break; }
            Bench.Type(ch);
            Bench.Settle(Delay / 10);
        }
        if (!lost) {
            Bench.Settle(Delay);
            if (commit == Commit.SpaceEnter && undisturbed()) { Bench.Press(0x20, false); Bench.Settle(Delay * 2); }
            if (commit != Commit.None && undisturbed()) Bench.Press(0x0D, false);
            Bench.Settle(Delay * 2);
            lost = !undisturbed();
        }
        if (lost) {
            if (InFront()) Bench.Press(0x1B, false);   // drop what is half typed, in this window only
            touched = UserInput.Count != touches;
            return null;
        }
        return box.Text.Replace("\r", "").Replace("\n", "");
    }

    // A set to type in a mode, one output file each.
    class Job { public string set; public Mode mode; public List<string[]> rows; }

    static readonly string[] JapaneseKinds = { "ja", "ajimee", "jatypo", "postsja" };
    static readonly string[] MixKinds = { "mixB", "mixC", "postsmixB", "postsmixC" };
    static readonly string[] EnglishKinds = { "en", "enclean", "postsen", "postsentypo" };

    Mode ModeByKey(string key) { return Modes.First(m => m.key == key); }

    List<string[]> Rows(string set) {
        return File.ReadAllLines(Path.Combine(setsDir, set + ".tsv"), Encoding.UTF8).Select(l => l.Split('\t')).Where(f => f.Length >= 4).ToList();
    }

    bool Ready() {
        if (!learnOn.Checked && !learnOff.Checked) {
            MessageBox.Show(this, L("chooseLearning"), "IME精度測定", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return false;
        }
        return true;
    }

    // One set in the chosen mode.
    void Measure() {
        if (setBox.SelectedItem == null || !Ready()) return;
        string set = (string)setBox.SelectedItem;
        var mode = Modes[modeBox.SelectedIndex];
        var job = new Job { set = set, mode = mode, rows = Rows(set) };
        Run(new List<List<Job>> { new List<Job> { job } }, mode.key, null);
    }

    // Every set, in three stages (Japanese, Japanese with English, English); the
    // person puts the input method in each stage's mode, or skips a mode it lacks.
    void MeasureAll() {
        if (!Ready()) return;
        var chosen = Modes[modeBox.SelectedIndex];
        bool auto = chosen.commit == Commit.Enter;   // an input method that converts as it goes
        var stages = new List<List<Job>>();
        foreach (var stage in new[] {
            new { kinds = JapaneseKinds, mode = ModeByKey(auto ? "live" : "jp") },
            new { kinds = MixKinds, mode = ModeByKey(auto ? "mixlive" : "mix") },
            new { kinds = EnglishKinds, mode = ModeByKey("auto") } }) {
            var jobs = kinds.Keys.Where(k => stage.kinds.Contains(kinds[k])).OrderBy(k => k)
                            .Select(k => new Job { set = k, mode = stage.mode, rows = Rows(k) }).ToList();
            if (jobs.Count > 0) stages.Add(jobs);
        }
        Run(stages, "all", stages.Count > 1 ? (Func<List<Job>, bool>)AskStage : null);
    }

    bool AskStage(List<Job> stage) {
        string what = L(EnglishKinds.Contains(kinds[stage[0].set]) ? "stageEn" : MixKinds.Contains(kinds[stage[0].set]) ? "stageMix" : "stageJa");
        var answer = MessageBox.Show(this, string.Format(L("stagePrompt"), what, stage.Count), "IME精度測定", MessageBoxButtons.YesNo, MessageBoxIcon.Question);
        Native.SetForegroundWindow(Handle);
        box.Focus();
        return answer == DialogResult.Yes;
    }

    void Run(List<List<Job>> stages, string runKey, Func<List<Job>, bool> ask) {
        string name = Regex.Replace(nameBox.Text.ToLowerInvariant(), "[^a-z0-9]+", "");
        if (name == "") name = "ime";
        foreach (Control c in new Control[] { setBox, modeBox, learnOn, learnOff, nameBox, start, all }) c.Enabled = false;
        stop.Enabled = true; openFolder.Visible = false; stopping = false;
        poll.Stop();
        ReadIme();
        var started = DateTime.Now;
        string runDir = Path.Combine(resultsDir, started.ToString("yyyyMMdd-HHmmss") + "-" + name + "-" + runKey);
        Directory.CreateDirectory(Path.Combine(runDir, "out"));
        pausedSeconds = 0;
        int total = stages.Sum(st => st.Sum(j => j.rows.Count)), done = 0;
        double typingSeconds = 0;
        bar.Maximum = Math.Max(1, total); bar.Value = 0;
        var measured = new List<Job>();
        bool complete = true;

        foreach (var stage in stages) {
            if (stopping) break;
            if (ask != null && !ask(stage)) {
                total -= stage.Sum(j => j.rows.Count);
                bar.Maximum = Math.Max(1, Math.Max(total, done));
                continue;
            }
            ReadIme();
            foreach (var job in stage) {
                if (stopping) break;
                // Three rows first: Japanese that stays romaji means the input method is
                // not converting (wrong mode, or a part of it not running).
                if (JapaneseKinds.Contains(kinds[job.set]) && job.mode.commit != Commit.None) {
                    int romaji = 0;
                    status.Text = L("probe");
                    for (int i = 0; i < Math.Min(3, job.rows.Count); i++) {
                        var t = TypeRow(job.rows[i][2], job.mode.commit);
                        if (t != null && Regex.IsMatch(t, "[a-z]{4}")) romaji++;
                    }
                    if (romaji >= 2) {
                        MessageBox.Show(this, L("notConverting"), "IME精度測定", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                        stopping = true;
                        break;
                    }
                }
                string system = "real." + name + "-" + job.mode.key;
                var outPath = Path.Combine(runDir, "out", system + "__" + job.set + ".tsv");
                int jobDone = 0;
                var jobStart = DateTime.Now;
                using (var w = new StreamWriter(outPath, false, new UTF8Encoding(false))) {
                    foreach (var f in job.rows) {
                        if (stopping) break;
                        string text = null;
                        for (int attempt = 0; text == null && attempt < 5 && !stopping; attempt++) {
                            text = TypeRow(f[2], job.mode.commit);
                            if (touched) attempt--;   // a person using the PC does not use up a try
                        }
                        if (text == null) break;
                        w.Write(f[0] + "\t" + f[1] + "\t" + text + "\n");
                        jobDone++; done++;
                        bar.Value = Math.Min(bar.Maximum, done);
                        double perRow = (typingSeconds + (DateTime.Now - jobStart).TotalSeconds - pausedSeconds) / done;
                        var left = TimeSpan.FromSeconds(perRow * (total - done));
                        string leftText = left.TotalMinutes >= 1 ? string.Format(L("minutes"), Math.Ceiling(left.TotalMinutes)) : string.Format(L("seconds"), Math.Ceiling(left.TotalSeconds));
                        status.Text = job.set + "　" + string.Format(L("progress"), done, total, leftText, total - done);
                    }
                }
                typingSeconds += (DateTime.Now - jobStart).TotalSeconds;
                if (jobDone > 0) measured.Add(job);
                if (jobDone < job.rows.Count) complete = false;
            }
        }
        if (stopping) complete = false;
        if (measured.Count > 0) WriteMeta(runDir, measured, started, complete);
        Finish(runDir, complete && measured.Count > 0);
    }

    void Finish(string runDir, bool complete) {
        foreach (Control c in new Control[] { setBox, modeBox, learnOn, learnOff, nameBox, start, all }) c.Enabled = true;
        stop.Enabled = false;
        lastRun = runDir;
        openFolder.Visible = true;
        status.Text = (complete ? L("done") : L("stopped")) + runDir;
        poll.Start();
    }

    static string J(string s) {
        var b = new StringBuilder("\"");
        foreach (char c in s ?? "") {
            if (c == '"' || c == '\\') b.Append('\\').Append(c);
            else if (c < 0x20) b.AppendFormat("\\u{0:x4}", (int)c);
            else b.Append(c);
        }
        return b.Append('"').ToString();
    }

    static string Sha256(byte[] data) {
        using (var h = SHA256.Create()) return string.Concat(h.ComputeHash(data).Select(x => x.ToString("x2")));
    }

    void WriteMeta(string runDir, List<Job> jobs, DateTime started, bool complete) {
        string harness = Sha256(File.ReadAllBytes(Application.ExecutablePath)).Substring(0, 12);
        var cv = Registry.LocalMachine.OpenSubKey(@"SOFTWARE\Microsoft\Windows NT\CurrentVersion");
        string product = cv == null ? "Windows" : (cv.GetValue("ProductName") as string ?? "Windows");
        int build;
        // Windows 11 still says "Windows 10" in ProductName; its builds start at 22000.
        if (cv != null && int.TryParse(cv.GetValue("CurrentBuild") as string, out build) && build >= 22000) product = product.Replace("Windows 10", "Windows 11");
        string windows = cv == null ? "?" : string.Format("{0} {1} build {2}.{3}", product, cv.GetValue("DisplayVersion"), cv.GetValue("CurrentBuild"), cv.GetValue("UBR"));
        string name = Regex.Replace(nameBox.Text.ToLowerInvariant(), "[^a-z0-9]+", "");
        var json = new StringBuilder("{\n");
        json.Append(" \"date\": " + J(started.ToString("yyyy-MM-dd HH:mm")) + ",\n");
        json.Append(" \"windows\": " + J(windows) + ",\n");
        json.Append(" \"imes\": { " + J(name) + ": { \"product\": " + J(imeProduct) + ", \"version\": " + J(imeVersion) + ", \"dll\": " + J(imeDll) +
                    ", \"clsid\": " + J(imeClsid.ToString()) + ", \"profile\": " + J(imeProfile.ToString()) + " } },\n");
        json.Append(" \"modes\": { " + string.Join(", ", jobs.Select(j => J(j.set) + ": " + J(j.mode.key))) + " },\n");
        json.Append(" \"learning\": " + J(learnOn.Checked ? "on" : "off") + ",\n");
        json.Append(" \"sets_sha256\": { " + string.Join(", ", jobs.Select(j => J(j.set) + ": " + J(Sha256(File.ReadAllBytes(Path.Combine(setsDir, j.set + ".tsv")))))) + " },\n");
        json.Append(" \"complete\": " + (complete ? "true" : "false") + ",\n");
        json.Append(" \"harness\": " + J("ImeBench " + harness) + "\n}\n");
        File.WriteAllText(Path.Combine(runDir, "meta.json"), json.ToString(), new UTF8Encoding(false));
    }
}
