# Several input methods and sets in one go, without the window (for
# maintainers): ImeBench.exe activates each input method for its own window
# by its TSF IDs and types the keys. Slow (minutes per set). Touching the
# mouse or keys pauses it until they have been still for 5 s. The usual way
# to measure is the window (ImeBench.exe without arguments).
#
#   .\realime.ps1 [-Group dev|heldout] [-Imes msime,google,...] [-Sets a,b] [-Limit N] [-Learning on|off] [-Note "..."]
#
# Each input method must already be in the Windows input list. Then:
#   python bench.py check <this run>; python bench.py score <this run>
param(
    [ValidateSet("dev", "heldout")][string]$Group = "dev",
    [string[]]$Imes = @("tekito", "tekitolive", "tekitomix", "msime", "google", "copilot", "mozc", "meltype"),
    [string[]]$Sets,
    [int]$Limit = 100000,
    [string]$Note = "",
    # Whether the input methods' learning was on. The bench does not change it;
    # say what it was (the published primary condition is "off").
    [ValidateSet("on", "off")][string]$Learning = "on",
    # AJIMEE-Bench's left context, put in the box before typing. Off: the input
    # methods measured did not read it (2026-10-12); kept for a later try.
    [switch]$Context
)
$ErrorActionPreference = "Stop"
$K = $PSScriptRoot
# Public repository: runner\ next to sets\, results\ and tools\.
$public = (Split-Path $K -Leaf) -eq "runner"
$root = if ($public) { Split-Path $K } else { $K }
$lib = if ($public) { "$root\tools\lib" } else { "$K\lib" }
# clsid, profile, keys that put it in the mode (hex VKs), options, set kinds it runs.
# TEKITO: 1A (IME off) = Auto, then 1C (Henkan) = Japanese; F3 = to Mix; 1D in Auto = Direct.
$ja = @("ajimee", "ja", "jatypo", "postsja")
$mix = @("mixB", "mixC", "postsmixB", "postsmixC")
$en = @("en", "enclean", "postsen", "postsentypo")
$T = @("{6F67E5C8-A873-4B69-8EC3-26DF00F642F1}", "{2876747C-FA52-4CCC-B308-F406190F8CDE}")
$profiles = [ordered]@{
    tekito       = @{ ids = $T; keys = "1A,1C"; kinds = $ja }
    tekitolive   = @{ ids = $T; keys = "1A,1C"; live = $true; once = $true; kinds = $ja }
    tekitomix    = @{ ids = $T; keys = "1A,1C,F3"; once = $true; kinds = $ja + $mix }
    tekitoauto   = @{ ids = $T; keys = "1A"; once = $true; english = $true; kinds = $en }
    tekitodirect = @{ ids = $T; keys = "1A,1D"; once = $true; english = $true; kinds = $en }
    # Japanese with English typed with the mode switched: to Direct and back to Japanese.
    tekitoswitch = @{ ids = $T; keys = "1A,1C"; once = $true; switch = "1A,1D;1C"; kinds = $mix }
    msime        = @{ ids = @("{03b5835f-f03c-411b-9ce2-aa23e1171e36}", "{A76C93D9-5523-4E90-AAFA-4DB112F9AC76}"); keys = "16"; switch = "19"; kinds = $ja + $mix }
    google       = @{ ids = @("{D5A86FD5-5308-47EA-AD16-9C4EB160EC3C}", "{773EB24E-CA1D-4B1B-B420-FA985BB0B80D}"); keys = "16"; switch = "19"; kinds = $ja + $mix }
    copilot      = @{ ids = @("{D4E1A2B3-5F6C-4D7E-8A9B-0C1D2E3F4A5B}", "{A1B2C3D4-E5F6-7890-1234-56789ABCDEF0}"); keys = "16"; switch = "19"; kinds = $ja + $mix }
    mozc         = @{ ids = @("{10A67BC8-22FA-4A59-90DC-2546652C56BF}", "{186F700C-71CF-43FE-A00E-AACB1D9E6D3D}"); keys = "16"; switch = "19"; kinds = $ja + $mix }
    meltype      = @{ ids = @("{417D801B-A9BD-4C26-BD16-356A825A6998}", "{21F643F4-72D5-4946-BF70-0A126AB52D05}"); keys = "16"; live = $true; kinds = $ja + $mix + $en }
}

if ($Group -eq "heldout") {
    $cycle = (Get-Content "$K\heldout\current.txt").Trim()
    $setDir = "$K\heldout\$cycle\sets"; $ext = ".tsv.gz"
} else {
    $setDir = if ($public) { "$root\sets" } else { "$K\dev\sets" }; $ext = ".tsv"
}
$kinds = Get-Content "$setDir\sets.json" -Raw | ConvertFrom-Json -AsHashtable
if (-not $Sets) { $Sets = $kinds.Keys | Sort-Object }
$runId = (Get-Date -Format "yyyyMMdd-HHmmss") + "-real"
$run = if ($public) { "$root\results\$runId" } else { "$K\$Group\runs\$runId" }
New-Item -ItemType Directory -Force "$run\out" | Out-Null
$work = if ($Group -eq "heldout") { "$K\heldout\tmp_$runId" } else { "$run\work" }
New-Item -ItemType Directory -Force $work | Out-Null

# Which input methods are in the input list now.
$tips = (Get-WinUserLanguageList | ForEach-Object { $_.InputMethodTips }) -join " "
$done = @(); $skipped = @(); $imeInfo = [ordered]@{}; $setHash = [ordered]@{}
# What each input method is: the DLL its TSF class loads, its version and date.
function Ime-Info($clsid) {
    $dll = (Get-ItemProperty "Registry::HKEY_CLASSES_ROOT\CLSID\$clsid\InprocServer32" -ErrorAction SilentlyContinue).'(default)'
    if (-not $dll -or -not (Test-Path $dll)) { return @{ dll = "$dll"; version = "?" } }
    $item = Get-Item $dll
    # The user's folders as variables: a published result does not carry the user name.
    $shown = $dll.Replace($env:LOCALAPPDATA, "%LOCALAPPDATA%").Replace($env:USERPROFILE, "%USERPROFILE%")
    @{ dll = $shown; version = "$($item.VersionInfo.FileVersion)"; modified = $item.LastWriteTime.ToString("s") }
}
$cv = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion"
# Windows 11 still says "Windows 10" in ProductName; its builds start at 22000.
$product = if ([int]$cv.CurrentBuild -ge 22000) { $cv.ProductName -replace "Windows 10", "Windows 11" } else { $cv.ProductName }
$windows = "$product $($cv.DisplayVersion) build $($cv.CurrentBuild).$($cv.UBR)"
# Rows of the whole batch, for the progress the bench window shows.
function Set-Rows([string]$s) {
    $n = if ($ext -eq ".tsv.gz") {
        $in = [IO.File]::OpenRead("$setDir\$s$ext")
        $r = New-Object IO.StreamReader((New-Object IO.Compression.GZipStream($in, [IO.Compression.CompressionMode]::Decompress)))
        $c = 0; while ($null -ne ($l = $r.ReadLine())) { if (($l -split "`t").Count -ge 4) { $c++ } }; $r.Close(); $c
    } else { @(Get-Content "$setDir\$s$ext" -Encoding utf8 | Where-Object { ($_ -split "`t").Count -ge 4 }).Count }
    [Math]::Min($n, $Limit)
}
$batchRows = 0; $rowsDone = 0; $jobs = 0; $jobNo = 0
foreach ($ime in $Imes) { foreach ($s in $Sets) { if ($kinds[$s] -in $profiles[$ime].kinds) { $batchRows += Set-Rows $s; $jobs++ } } }
$env:IMEBENCH_TOTAL = "$batchRows"

foreach ($ime in $Imes) {
    $p = $profiles[$ime]
    if (-not $p) { throw "no profile $ime" }
    if ($tips -notmatch [regex]::Escape("$($p.ids[0])$($p.ids[1])")) {
        $skipped += "$ime (not in the Windows input list)"
        continue
    }
    # TEKITO's live conversion is a setting (user.db): on for the live
    # profile, off for the others, and put back to the user's value at the end.
    if ($ime -like "tekito*") {
        $want = if ($ime -eq "tekitolive") { 1 } else { 0 }
        $was = python "$lib\set_live.py" $want
        if ($null -eq $script:liveWas) { $script:liveWas = $was }
        Start-Sleep -Seconds 2
    }
    $env:IMEBENCH_KEYS = $p.keys
    $env:IMEBENCH_LIVE = if ($p.live) { "1" } else { "0" }
    $env:IMEBENCH_KEYS_ONCE = if ($p.once) { "1" } else { "0" }
    $env:IMEBENCH_ENGLISH = if ($p.english) { "1" } else { "0" }
    $env:IMEBENCH_CONVERT_KEY = "0"
    $env:IMEBENCH_SWITCH = if ($p.switch) { $p.switch } else { "19" }
    foreach ($s in $Sets) {
        if ($kinds[$s] -notin $p.kinds) { continue }
        # Cycle 3: Japanese with English typed with the mode switched ("...2" sets, keys
        # with "|") goes to every input method with a switch key; typed in one mode
        # (the other mix sets) only to the input methods that take it.
        $switched = $s -match "^(mix|postsmix).*2$"
        if ($kinds[$s] -in $mix -and ($switched -xor [bool]$p.switch)) { continue }
        $keys = "$work\${s}_keys.tsv"
        if (-not (Test-Path $keys)) {
            if ($ext -eq ".tsv.gz") {
                $in = [IO.File]::OpenRead("$setDir\$s$ext")
                $gz = New-Object IO.Compression.GZipStream($in, [IO.Compression.CompressionMode]::Decompress)
                $o = [IO.File]::Create($keys); $gz.CopyTo($o); $o.Close(); $gz.Close(); $in.Close()
            } else { Copy-Item "$setDir\$s$ext" $keys }
        }
        # Left context (AJIMEE-Bench): put in the box before the keys are typed.
        $env:IMEBENCH_CONTEXT = if (($Context -or $s -like "*ctx*") -and (Test-Path "$setDir\$s.context.tsv")) { "$setDir\$s.context.tsv" } else { "" }
        $setHash[$s] = (Get-FileHash $keys -Algorithm SHA256).Hash.ToLower()
        $imeInfo[$ime] = Ime-Info $p.ids[0]
        $out = "$work\real.$ime`__$s.tsv"
        # Probe: three rows first. Japanese that comes out as romaji means the
        # input method is not converting at all (e.g. Meltype without its
        # Meltype.exe running); measuring it would only record the setup.
        if ($kinds[$s] -in $ja) {
            Start-Process "$K\ImeBench.exe" -ArgumentList $p.ids[0], $p.ids[1], "`"$keys`"", "`"$work\probe.tsv`"", 3 -Wait
            $probe = @(Get-Content "$work\probe.tsv" -Encoding utf8 -ErrorAction SilentlyContinue)
            $romaji = @($probe | Where-Object { ($_ -split "`t")[2] -cmatch "[a-z]{4}" }).Count
            if ($probe.Count -eq 0 -or $romaji -ge 2) {
                $skipped += "$ime/$s (probe: Japanese not converted, $romaji of $($probe.Count) rows as romaji)"
                "$ime $s`: not converting, skipped"
                continue
            }
        }
        $start = Get-Date
        $jobNo++
        $env:IMEBENCH_LABEL = "$ime $s ($jobNo/$jobs)"
        $env:IMEBENCH_BEFORE = "$rowsDone"
        Start-Process "$K\ImeBench.exe" -ArgumentList $p.ids[0], $p.ids[1], "`"$keys`"", "`"$out`"", $Limit -Wait
        $rowsDone += Set-Rows $s
        "{0} {1}: {2:N1} min" -f $ime, $s, ((Get-Date) - $start).TotalMinutes
        if ($Group -eq "heldout") {
            $in = [IO.File]::OpenRead($out); $o = [IO.File]::Create("$run\out\real.$ime`__$s.tsv.gz")
            $gz = New-Object IO.Compression.GZipStream($o, [IO.Compression.CompressionLevel]::Optimal)
            $in.CopyTo($gz); $gz.Close(); $o.Close(); $in.Close()
        } else { Move-Item $out "$run\out\" }
        # When each row was typed, for the check that it was typed at all.
        New-Item -ItemType Directory -Force "$run\times" | Out-Null
        if (Test-Path "$out.times") { Move-Item "$out.times" "$run\times\real.$ime`__$s.tsv" }
        $done += "$ime/$s"
    }
}
if ($null -ne $script:liveWas -and $script:liveWas -ne "") {
    python "$lib\set_live.py" $script:liveWas | Out-Null
}
Remove-Item -Recurse -Force $work
@{ group = $Group; kind = "real-ime"; note = $Note; date = (Get-Date -Format "yyyy-MM-dd HH:mm"); done = $done; skipped = $skipped
   windows = $windows; imes = $imeInfo; learning = $Learning; sets_sha256 = $setHash
   harness = "ImeBench " + (Get-FileHash "$K\ImeBench.exe").Hash.Substring(0, 12).ToLower() } |
    ConvertTo-Json -Depth 4 | Set-Content "$run\meta.json" -Encoding utf8NoBOM
# The hash of every file as measured: the check sees any later edit.
Get-ChildItem $run -Recurse -File | Where-Object Name -ne "manifest.sha256" | Sort-Object FullName |
    ForEach-Object { "{0}  {1}" -f (Get-FileHash $_.FullName).Hash.ToLower(), $_.FullName.Substring($run.Length + 1).Replace("\", "/") } |
    Set-Content "$run\manifest.sha256" -Encoding utf8NoBOM
if ($skipped) { "skipped: " + ($skipped -join "; ") }
"real-IME outputs in $run; score with: python bench.py score <engine run> --with $run"
