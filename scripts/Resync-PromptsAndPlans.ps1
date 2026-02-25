<#
.SYNOPSIS
    Resync-PromptsAndPlans.ps1 - DFW-aware file sequencing and dependency graph generation

.DESCRIPTION
    Reusable utility for any DevFlywheel (DFW) project. Two phases:
    1. Phase 1 (Sequence): Per-directory sequencing with NNN-type-slug.md pattern.
    2. Phase 2 (Graph): Generates DEPENDENCY_GRAPH.md with Mermaid diagram and index.

    Use -PhaseSequence or -PhaseGraph to run only one phase. Default: both.
    All paths are relative to -ProjectRoot. No hardcoded project-specific names.

    DFW-aware: reads .dfw/project.json when available, stores caches in .dfw/,
    auto-discovers DFW content directories, and skips structural files (prefixed _).

.PARAMETER ProjectRoot
    Root directory of the project. Defaults to current directory.

.PARAMETER Directories
    Subdirectories to scan (relative to ProjectRoot).
    Default: auto-discovers DFW content directories (docs, plans, prompts, context, research).

.PARAMETER GraphOutputFile
    Path to the graph output file (relative to ProjectRoot).
    Default: docs/DEPENDENCY_GRAPH.md

.PARAMETER SkipUnderscorePrefix
    Skip files prefixed with _ (DFW structural files). Default: true.

.PARAMETER DryRun
    Preview changes without writing files or renaming.

.PARAMETER Force
    Ignore caches (re-sequence / regenerate graph).

.PARAMETER PhaseSequence
    Run only the file sequencing phase.

.PARAMETER PhaseGraph
    Run only the graph generation phase.

.EXAMPLE
    .\Resync-PromptsAndPlans.ps1
.EXAMPLE
    .\Resync-PromptsAndPlans.ps1 -ProjectRoot "X:\MyProject" -DryRun
.EXAMPLE
    .\Resync-PromptsAndPlans.ps1 -ProjectRoot "X:\MyProject" -Directories @("docs","plans","custom-dir") -PhaseGraph
.EXAMPLE
    .\Resync-PromptsAndPlans.ps1 -PhaseSequence -Force
.NOTES
    Caches: .dfw/.resync-sequence-cache.json, .dfw/.resync-graph-cache.json
    Conforms to DevFlywheel methodology v1.0
    Version: 2.0.0
#>

param(
    [string]$ProjectRoot = (Get-Location).Path,
    [string[]]$Directories = @(),
    [string]$GraphOutputFile = "docs\DEPENDENCY_GRAPH.md",
    [bool]$SkipUnderscorePrefix = $true,
    [switch]$DryRun,
    [switch]$Force,
    [switch]$PhaseSequence,
    [switch]$PhaseGraph,
    [switch]$Verbose
)

# =============================================================================
#      CONFIGURATION
# =============================================================================
$SequenceDigits = 3

# DFW canonical content directories (used for auto-discovery)
$DfwContentDirs = @("docs", "plans", "prompts", "context", "research")

# Cache file paths (stored in .dfw/)
$SyncCacheRelPath  = ".dfw\.resync-sequence-cache.json"
$GraphCacheRelPath = ".dfw\.resync-graph-cache.json"

# Type patterns — order matters for detection (more specific first)
$TypePatterns = @{
    "retro"     = @("retrospective", "retro")
    "handoff"   = @("handoff", "context-handoff", "context_handoff")
    "decision"  = @("decision", "decisions-log", "decisions_log")
    "adr"       = @("\badr\b", "architecture-decision")
    "journal"   = @("journal", "ifs_journal", "development_journal")
    "note"      = @("\.note\.", "\bnotes\b")
    "plan"      = @("plan", "\.plan\.md$", "roadmap", "wishlist", "todo", "backlog", "sprint")
    "prompt"    = @("prompt", "persona", "system-prompt")
    "context"   = @("active-context", "active_context", "\bcontext\b")
    "spec"      = @("\bspec\b", "\bspecification\b", "\.spec\.md$")
    "research"  = @("research", "findings", "literature", "study")
    "analysis"  = @("analysis", "analyze", "review")
    "output"    = @("output", "result", "report")
    "doc"       = @("doc", "readme", "guide", "setup", "overview", "architecture", "changelog", "reference")
}

# Fixed detection order — more specific types checked first
$TypeOrder = @(
    "retro", "handoff", "decision", "adr", "journal", "note",
    "plan", "prompt", "context", "spec", "research", "analysis", "output", "doc"
)

# Display names for types (used in graph output)
$TypeNames = @{
    "retro"     = "Retrospective"
    "handoff"   = "Handoff"
    "decision"  = "Decision"
    "adr"       = "ADR"
    "journal"   = "Journal"
    "note"      = "Note"
    "plan"      = "Plan"
    "prompt"    = "Prompt"
    "context"   = "Context"
    "spec"      = "Specification"
    "research"  = "Research"
    "analysis"  = "Analysis"
    "output"    = "Output"
    "doc"       = "Documentation"
}

# Files to always skip from sequencing
$SkipPatterns = @(
    "^README\.md$",
    "^CHANGELOG\.md$",
    "^ARCHITECTURE\.md$",
    "^PROJECT_OVERVIEW\.md$",
    "^DEPENDENCY_GRAPH\.md$",
    "^PROMPT_OUTPUT_GRAPH\.md$",
    "^LICENSE",
    "^\..*",
    "\.cache\.json$",
    "\.resync-.*\.json$"
)

# =============================================================================
#      DFW PROJECT DETECTION
# =============================================================================
function Get-DfwManifest {
    param([string]$Root)
    $dfwPath = Join-Path $Root ".dfw\project.json"
    $legacyPath = Join-Path $Root ".devflywheel\project.json"

    $manifestPath = $null
    if (Test-Path $dfwPath) { $manifestPath = $dfwPath }
    elseif (Test-Path $legacyPath) { $manifestPath = $legacyPath }

    if ($manifestPath) {
        try {
            $content = Get-Content $manifestPath -Raw | ConvertFrom-Json
            return $content
        } catch {
            Write-Host "  Warning: Could not parse $manifestPath" -ForegroundColor Yellow
            return $null
        }
    }
    return $null
}

function Get-DfwMetadataDir {
    param([string]$Root)
    $dfwDir = Join-Path $Root ".dfw"
    $legacyDir = Join-Path $Root ".devflywheel"
    if (Test-Path $dfwDir) { return $dfwDir }
    if (Test-Path $legacyDir) { return $legacyDir }
    # Default to .dfw even if it doesn't exist yet
    return $dfwDir
}

# =============================================================================
#      SHARED HELPER FUNCTIONS
# =============================================================================
function Write-Header {
    param([string]$Text, [string]$Style = "Major")
    $Width = 60
    $Line = if ($Style -eq "Major") { "=" * $Width } else { "-" * $Width }
    $Color = if ($Style -eq "Major") { "Blue" } else { "Green" }
    Write-Host ""
    Write-Host $Line -ForegroundColor $Color
    Write-Host "     $Text" -ForegroundColor $Color
    Write-Host $Line -ForegroundColor $Color
}

function Write-Status {
    param([string]$Label, [string]$Value, [string]$ValueColor = "White")
    Write-Host "  $Label`: " -ForegroundColor Gray -NoNewline
    Write-Host $Value -ForegroundColor $ValueColor
}

function Write-Change {
    param([string]$OldName, [string]$NewName, [string]$Action = "RENAME")
    $Color = switch ($Action) {
        "RENAME" { "Yellow" }
        "SKIP"   { "DarkGray" }
        "NEW"    { "Green" }
        "ERROR"  { "Red" }
        default  { "White" }
    }
    Write-Host "  [$Action] " -ForegroundColor $Color -NoNewline
    Write-Host "$OldName" -ForegroundColor White -NoNewline
    if ($NewName -and $Action -eq "RENAME") {
        Write-Host " -> " -ForegroundColor DarkGray -NoNewline
        Write-Host $NewName -ForegroundColor Cyan
    } else {
        Write-Host ""
    }
}

function Get-TrackingCache {
    param([string]$CachePath)
    if (Test-Path $CachePath) {
        try {
            $Content = Get-Content $CachePath -Raw | ConvertFrom-Json
            $Cache = @{}
            $Content.PSObject.Properties | ForEach-Object { $Cache[$_.Name] = $_.Value }
            return $Cache
        } catch {
            if ($Verbose) { Write-Host "  Warning: Could not read cache, starting fresh" -ForegroundColor Yellow }
            return @{}
        }
    }
    return @{}
}

function Save-TrackingCache {
    param([string]$CachePath, [hashtable]$Cache)
    $CacheDir = Split-Path $CachePath -Parent
    if (-not (Test-Path $CacheDir)) {
        New-Item -ItemType Directory -Path $CacheDir -Force | Out-Null
    }
    $Cache | ConvertTo-Json -Depth 10 | Out-File -FilePath $CachePath -Encoding UTF8
}

function Get-FileSignature {
    param([string]$Path)
    $FileInfo = Get-Item $Path
    return "$($FileInfo.Length)_$($FileInfo.LastWriteTime.Ticks)"
}

# =============================================================================
#      PHASE 1: SEQUENCING HELPERS
# =============================================================================
function Get-FileType {
    param([string]$FileName)
    $LowerName = $FileName.ToLower()
    foreach ($type in $TypeOrder) {
        if (-not $TypePatterns.ContainsKey($type)) { continue }
        foreach ($pattern in $TypePatterns[$type]) {
            if ($LowerName -match $pattern) { return $type }
        }
    }
    return "doc"
}

function Test-ShouldSkip {
    param([string]$FileName)
    # Skip by pattern
    foreach ($pattern in $SkipPatterns) {
        if ($FileName -match $pattern) { return $true }
    }
    # Skip underscore-prefixed DFW structural files
    if ($SkipUnderscorePrefix -and $FileName.StartsWith("_")) { return $true }
    return $false
}

function Test-AlreadySequenced {
    param([string]$FileName)
    return $FileName -match "^\d{3}-\w+-"
}

function New-SequencedName {
    param([string]$OriginalName, [int]$Sequence, [string]$Type, [int]$Digits = 3)
    $SeqStr = $Sequence.ToString().PadLeft($Digits, '0')
    # Strip existing sequence prefix if present
    $CleanName = $OriginalName -replace "^\d{2,3}-\w+-", ""
    $BaseName = [System.IO.Path]::GetFileNameWithoutExtension($CleanName)
    $Slug = $BaseName -replace '[^\w\s-]', '' -replace '\s+', '-' -replace '-+', '-' -replace '^-|-$', ''
    $Slug = $Slug.ToLower()
    # Remove leading type token if it duplicates what we're about to add
    $Slug = $Slug -replace "^$Type-", ""
    if ([string]::IsNullOrWhiteSpace($Slug)) { $Slug = "untitled" }
    return "$SeqStr-$Type-$Slug.md"
}

# =============================================================================
#      PHASE 2: GRAPH HELPERS
# =============================================================================
function Get-FileNameParts {
    param([string]$FileName)
    $Result = @{ Sequence = $null; Type = "doc"; Name = $FileName; IsSequenced = $false }
    if ($FileName -match "^(\d{3})-(\w+)-(.+)\.md$") {
        $Result.Sequence = [int]$matches[1]
        $Result.Type = $matches[2]
        $Result.Name = $matches[3]
        $Result.IsSequenced = $true
    } elseif ($FileName -match "^(.+)\.md$") {
        $Result.Name = $matches[1]
    }
    return $Result
}

function Get-FrontMatter {
    param([string]$FilePath)
    $Result = @{
        HasFrontMatter = $false; Type = $null; SourcePrompt = $null; Created = $null
        Description = $null; Theme = $null; SessionId = $null; Name = $null
        Overview = $null; Iteration = $null; Phase = $null; Source = $null
    }
    try {
        $Content = Get-Content $FilePath -Raw -ErrorAction Stop
        if ($Content -match '(?s)^---\s*\r?\n(.+?)\r?\n---') {
            $Result.HasFrontMatter = $true
            $FrontMatter = $matches[1]
            if ($FrontMatter -match '(?m)^type:\s*(.+?)$') { $Result.Type = $matches[1].Trim() }
            if ($FrontMatter -match '(?m)^source_prompt:\s*(.+?)$') { $Result.SourcePrompt = $matches[1].Trim() }
            if ($FrontMatter -match '(?m)^created:\s*(.+?)$') { $Result.Created = $matches[1].Trim() }
            if ($FrontMatter -match '(?m)^description:\s*(.+?)$') { $Result.Description = $matches[1].Trim() }
            if ($FrontMatter -match '(?m)^theme:\s*(.+?)$') { $Result.Theme = $matches[1].Trim() }
            if ($FrontMatter -match '(?m)^sessionId:\s*(.+?)$') { $Result.SessionId = $matches[1].Trim() }
            if ($FrontMatter -match '(?m)^name:\s*(.+?)$') { $Result.Name = $matches[1].Trim() }
            if ($FrontMatter -match '(?m)^overview:\s*(.+?)$') { $Result.Overview = $matches[1].Trim() }
            if ($FrontMatter -match '(?m)^iteration:\s*(.+?)$') { $Result.Iteration = $matches[1].Trim() }
            if ($FrontMatter -match '(?m)^phase:\s*(.+?)$') { $Result.Phase = $matches[1].Trim() }
            if ($FrontMatter -match '(?m)^source:\s*(.+?)$') { $Result.Source = $matches[1].Trim() }
        }
    } catch { }
    return $Result
}

function Get-DirectoryTheme {
    param([string]$Directory)
    # Derive theme from DFW canonical directory names
    $DirThemes = @{
        "docs"     = "Documentation and Specifications"
        "plans"    = "Plans and Roadmaps"
        "prompts"  = "Prompts and Handoffs"
        "context"  = "Context and Decisions"
        "research" = "Research and Analysis"
        "scripts"  = "Automation Scripts"
    }
    $leaf = Split-Path $Directory -Leaf
    if ($DirThemes.ContainsKey($leaf.ToLower())) {
        return $DirThemes[$leaf.ToLower()]
    }
    # Title-case the directory name as fallback
    $words = $leaf -split '[-_]' | ForEach-Object {
        if ($_.Length -gt 0) { $_.Substring(0,1).ToUpper() + $_.Substring(1).ToLower() } else { $_ }
    }
    return ($words -join " ")
}

# =============================================================================
#      PHASE 1: SEQUENCE FILES (per-directory by CreationTime)
# =============================================================================
function Invoke-PhaseSequence {
    $MetaDir = Get-DfwMetadataDir -Root $ProjectRoot
    $CachePath = Join-Path $ProjectRoot $SyncCacheRelPath
    $Cache = if ($Force) { @{} } else { Get-TrackingCache -CachePath $CachePath }

    $TotalStats = @{ Scanned = 0; Skipped = 0; AlreadySequenced = 0; Renamed = 0; Errors = 0 }

    foreach ($Dir in $Directories) {
        $FullPath = Join-Path $ProjectRoot $Dir
        if (-not (Test-Path $FullPath)) {
            if ($Verbose) { Write-Host "  Directory not found: $Dir" -ForegroundColor DarkGray }
            continue
        }

        Write-Header "Sequencing: $Dir/" "Minor"

        # Gather .md files from this directory
        $Files = Get-ChildItem -Path $FullPath -Filter "*.md" -File -ErrorAction SilentlyContinue
        $Candidates = @()
        foreach ($File in $Files) {
            if (Test-ShouldSkip -FileName $File.Name) {
                $TotalStats.Skipped++
                if ($Verbose) { Write-Change -OldName "$Dir/$($File.Name)" -Action "SKIP" }
                continue
            }
            $Candidates += $File
        }

        # Sort by CreationTime within this directory
        $Candidates = $Candidates | Sort-Object CreationTime, LastWriteTime

        # Per-directory sequence counter
        $NextSeq = 1
        foreach ($File in $Candidates) {
            $RelativePath = Join-Path $Dir $File.Name
            $FileHash = Get-FileSignature -Path $File.FullName
            $CacheKey = $RelativePath
            $TotalStats.Scanned++

            $Type = Get-FileType -FileName $File.Name
            $NewName = New-SequencedName -OriginalName $File.Name -Sequence $NextSeq -Type $Type -Digits $SequenceDigits

            # Check if already correctly named and cached
            if ($File.Name -eq $NewName) {
                $Cache[$CacheKey] = $FileHash
                if ($Verbose) { Write-Host "  [OK] $($File.Name)" -ForegroundColor DarkGray }
                $TotalStats.AlreadySequenced++
                $NextSeq++
                continue
            }

            # Check cache — if cached and unchanged, still check if name is correct
            if ($Cache.ContainsKey($CacheKey) -and $Cache[$CacheKey] -eq $FileHash -and $File.Name -eq $NewName) {
                if ($Verbose) { Write-Host "  [OK] $($File.Name) (cached)" -ForegroundColor DarkGray }
                $TotalStats.AlreadySequenced++
                $NextSeq++
                continue
            }

            # Need to rename
            $NewPath = Join-Path $FullPath $NewName
            if ((Test-Path $NewPath -PathType Leaf) -and ($File.FullName -ne $NewPath)) {
                Write-Change -OldName "$Dir/$($File.Name)" -NewName "COLLISION: $NewName" -Action "ERROR"
                $TotalStats.Errors++
            } else {
                Write-Change -OldName "$Dir/$($File.Name)" -NewName $NewName -Action "RENAME"
                if (-not $DryRun) {
                    try {
                        Rename-Item -Path $File.FullName -NewName $NewName -ErrorAction Stop
                        $NewRelativePath = Join-Path $Dir $NewName
                        $NewFileHash = Get-FileSignature -Path (Join-Path $FullPath $NewName)
                        $Cache[$NewRelativePath] = $NewFileHash
                        if ($Cache.ContainsKey($CacheKey) -and $CacheKey -ne $NewRelativePath) {
                            $Cache.Remove($CacheKey)
                        }
                        $TotalStats.Renamed++
                    } catch {
                        Write-Host "    ERROR: $($_.Exception.Message)" -ForegroundColor Red
                        $TotalStats.Errors++
                    }
                } else {
                    $TotalStats.Renamed++
                }
            }
            $NextSeq++
        }

        Write-Status "  $Dir files" "$($Candidates.Count) candidates, seq 001-$($NextSeq - 1)"
    }

    if (-not $DryRun) { Save-TrackingCache -CachePath $CachePath -Cache $Cache }

    Write-Header "SEQUENCE SUMMARY" "Major"
    Write-Status "Files scanned" $TotalStats.Scanned
    Write-Status "Files renamed" $TotalStats.Renamed $(if ($TotalStats.Renamed -gt 0) { "Green" } else { "White" })
    Write-Status "Already sequenced" $TotalStats.AlreadySequenced
    Write-Status "Skipped" $TotalStats.Skipped
    Write-Status "Errors" $TotalStats.Errors $(if ($TotalStats.Errors -gt 0) { "Red" } else { "Green" })
}

# =============================================================================
#      PHASE 2: GENERATE GRAPH
# =============================================================================
function Invoke-PhaseGraph {
    $CachePath = Join-Path $ProjectRoot $GraphCacheRelPath
    $OutputPath = Join-Path $ProjectRoot $GraphOutputFile

    $OutputDir = Split-Path $OutputPath -Parent
    if (-not (Test-Path $OutputDir)) {
        if (-not $DryRun) { New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null }
    }

    $Cache = if ($Force) { @{} } else { Get-TrackingCache -CachePath $CachePath }
    $NewCache = @{}
    $AllFiles = @()
    $DirectoryFiles = @{}

    # Get project name from manifest
    $ProjectName = Split-Path $ProjectRoot -Leaf

    foreach ($Dir in $Directories) {
        $FullPath = Join-Path $ProjectRoot $Dir
        if (-not (Test-Path $FullPath)) { continue }
        Write-Header "Scanning: $Dir/" "Minor"
        $Files = Get-ChildItem -Path $FullPath -Filter "*.md" -File -ErrorAction SilentlyContinue |
            Where-Object { -not (Test-ShouldSkip -FileName $_.Name) } |
            Sort-Object CreationTime
        $DirectoryFiles[$Dir] = @()

        foreach ($File in $Files) {
            $RelativePath = Join-Path $Dir $File.Name
            $FileHash = Get-FileSignature -Path $File.FullName
            $Parsed = Get-FileNameParts -FileName $File.Name
            $FrontMatter = Get-FrontMatter -FilePath $File.FullName
            $FileInfo = @{
                Path = $RelativePath; FullPath = $File.FullName; Name = $File.Name; Directory = $Dir
                Sequence = $Parsed.Sequence; Type = $Parsed.Type; CleanName = $Parsed.Name
                IsSequenced = $Parsed.IsSequenced; CreationTime = $File.CreationTime; LastWriteTime = $File.LastWriteTime
                FrontMatter = $FrontMatter
                IsNew = -not $Cache.ContainsKey($RelativePath)
                IsChanged = $Cache.ContainsKey($RelativePath) -and $Cache[$RelativePath] -ne $FileHash
            }
            $AllFiles += $FileInfo
            $DirectoryFiles[$Dir] += $FileInfo
            $NewCache[$RelativePath] = $FileHash
            $StatusIcon = if ($FileInfo.IsNew) { "[NEW]" } elseif ($FileInfo.IsChanged) { "[CHG]" } else { "[OK]" }
            $StatusColor = if ($FileInfo.IsNew) { "Green" } elseif ($FileInfo.IsChanged) { "Yellow" } else { "DarkGray" }
            if ($Verbose -or $FileInfo.IsNew -or $FileInfo.IsChanged) {
                Write-Host "  $StatusIcon " -ForegroundColor $StatusColor -NoNewline
                Write-Host $File.Name -ForegroundColor White
            }
        }
        Write-Status "Files found" $Files.Count
    }

    Write-Header "Generating Dependency Graph" "Minor"

    $GraphContent = @"
# $ProjectName - Dependency Graph

**Generated:** $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
**Project:** $ProjectName
**Purpose:** Master reference showing relationships between prompts, plans, specifications, and outputs.

---

## Visual Dependency Graph

``````mermaid
graph TB
"@

    foreach ($Dir in $DirectoryFiles.Keys | Sort-Object) {
        $Files = $DirectoryFiles[$Dir]
        if ($Files.Count -eq 0) { continue }
        $Theme = Get-DirectoryTheme -Directory $Dir
        $SafeDir = $Dir -replace "[/\\]", "_"
        $GraphContent += @"

    subgraph $SafeDir ["$Dir/ - $Theme"]
"@
        $idx = 0
        foreach ($File in $Files) {
            $raw = ($File.CleanName -replace "[^a-zA-Z0-9]", "")
            if ([string]::IsNullOrEmpty($raw)) { $raw = "f$idx" }
            $CleanId = $raw.Substring(0, [Math]::Min(20, $raw.Length))
            $NodeId = "${SafeDir}_${CleanId}_${idx}"
            $idx++
            $DisplayName = if ($File.Sequence) {
                "$($File.Sequence.ToString().PadLeft(3,'0'))-$($File.Type)"
            } else {
                $File.CleanName.Substring(0, [Math]::Min(25, $File.CleanName.Length))
            }
            $GraphContent += @"

        ${NodeId}["$DisplayName"]
"@
        }
        $GraphContent += @"

    end
"@
    }

    $GraphContent += @"


    %% Relationships (source_prompt -> output)
"@
    foreach ($File in $AllFiles | Where-Object { $_.FrontMatter.SourcePrompt }) {
        $SourcePath = $File.FrontMatter.SourcePrompt
        $SourceFile = $AllFiles | Where-Object { $_.Path -eq $SourcePath -or $_.Name -eq (Split-Path $SourcePath -Leaf) } | Select-Object -First 1
        if ($SourceFile) {
            $srcIdx = [array]::IndexOf($AllFiles, $SourceFile)
            $tgtIdx = [array]::IndexOf($AllFiles, $File)
            $SourceSafeDir = $SourceFile.Directory -replace "[/\\]", "_"
            $SourceRaw = ($SourceFile.CleanName -replace "[^a-zA-Z0-9]", "")
            if ([string]::IsNullOrEmpty($SourceRaw)) { $SourceRaw = "f0" }
            $SourceCleanId = $SourceRaw.Substring(0, [Math]::Min(20, $SourceRaw.Length))
            $SourceNodeId = "${SourceSafeDir}_${SourceCleanId}_${srcIdx}"

            $TargetSafeDir = $File.Directory -replace "[/\\]", "_"
            $TargetRaw = ($File.CleanName -replace "[^a-zA-Z0-9]", "")
            if ([string]::IsNullOrEmpty($TargetRaw)) { $TargetRaw = "f0" }
            $TargetCleanId = $TargetRaw.Substring(0, [Math]::Min(20, $TargetRaw.Length))
            $TargetNodeId = "${TargetSafeDir}_${TargetCleanId}_${tgtIdx}"

            $GraphContent += @"

    $SourceNodeId --> $TargetNodeId
"@
        }
    }

    $GraphContent += @"

``````

---

## Directory Index

"@
    foreach ($Dir in $DirectoryFiles.Keys | Sort-Object) {
        $Files = $DirectoryFiles[$Dir]
        if ($Files.Count -eq 0) { continue }
        $Theme = Get-DirectoryTheme -Directory $Dir
        $GraphContent += @"

### $Dir/ - $Theme

| Seq | Type | Phase/Iter | File | Created | Description |
|-----|------|------------|------|---------|-------------|
"@
        foreach ($File in $Files | Sort-Object { $_.Sequence }, { $_.CreationTime }) {
            $Seq = if ($File.Sequence) { $File.Sequence.ToString().PadLeft(3, '0') } else { "-" }
            $TypeDisplay = if ($TypeNames.ContainsKey($File.Type)) { $TypeNames[$File.Type] } else { $File.Type }
            $PhaseIter = if ($File.FrontMatter.Phase) { $File.FrontMatter.Phase } elseif ($File.FrontMatter.Iteration) { $File.FrontMatter.Iteration } else { "-" }
            $Created = $File.CreationTime.ToString("yyyy-MM-dd")
            $Desc = if ($File.FrontMatter.Description) { $File.FrontMatter.Description } elseif ($File.FrontMatter.Overview) { $File.FrontMatter.Overview } elseif ($File.FrontMatter.Name) { $File.FrontMatter.Name } else { "-" }
            if ($Desc.Length -gt 50) { $Desc = $Desc.Substring(0, 47) + "..." }
            $GraphContent += "`n| $Seq | $TypeDisplay | $PhaseIter | ``$($File.Name)`` | $Created | $Desc |"
        }
        $GraphContent += "`n"
    }

    $GraphContent += @"

---

## Statistics

| Category | Count |
|----------|-------|
"@
    $TypeCounts = $AllFiles | Group-Object { $_.Type }
    foreach ($Group in $TypeCounts | Sort-Object Name) {
        $TypeDisplay = if ($TypeNames.ContainsKey($Group.Name)) { $TypeNames[$Group.Name] + "s" } else { $Group.Name }
        $GraphContent += "`n| **$TypeDisplay** | $($Group.Count) |"
    }
    $GraphContent += "`n| **Total Files** | $($AllFiles.Count) |"

    $GraphContent += @"

---

## Timeline Summary

| Date | Files Added/Modified |
|------|---------------------|
"@
    $ByDate = $AllFiles | Group-Object { $_.CreationTime.ToString("yyyy-MM-dd") } | Sort-Object Name -Descending | Select-Object -First 10
    foreach ($Group in $ByDate) {
        $FileNames = ($Group.Group | ForEach-Object { $_.CleanName.Substring(0, [Math]::Min(15, $_.CleanName.Length)) }) -join ", "
        if ($FileNames.Length -gt 60) { $FileNames = $FileNames.Substring(0, 57) + "..." }
        $GraphContent += "`n| $($Group.Name) | $FileNames |"
    }

    $GraphContent += @"

---

## Maintenance

To update this graph (and optionally re-sequence files), run:

``````powershell
.\scripts\Resync-PromptsAndPlans.ps1 -ProjectRoot "$ProjectRoot"
``````

Only graph:

``````powershell
.\scripts\Resync-PromptsAndPlans.ps1 -ProjectRoot "$ProjectRoot" -PhaseGraph
``````

Only sequence:

``````powershell
.\scripts\Resync-PromptsAndPlans.ps1 -ProjectRoot "$ProjectRoot" -PhaseSequence
``````

---

*Generated by Resync-PromptsAndPlans.ps1 v2.0.0 (DevFlywheel)*
"@

    if (-not $DryRun) {
        $GraphContent | Out-File -FilePath $OutputPath -Encoding UTF8
        Save-TrackingCache -CachePath $CachePath -Cache $NewCache
        Write-Status "Graph written to" $OutputPath "Green"
    } else {
        Write-Host ""
        Write-Host "  [DRY RUN] Would write to: $OutputPath" -ForegroundColor Yellow
    }

    Write-Header "GRAPH SUMMARY" "Major"
    Write-Status "Total files indexed" $AllFiles.Count
    Write-Status "New files" ($AllFiles | Where-Object { $_.IsNew }).Count "Green"
    Write-Status "Changed files" ($AllFiles | Where-Object { $_.IsChanged }).Count "Yellow"
    Write-Status "Output file" $OutputPath
}

# =============================================================================
#      MAIN
# =============================================================================
$RunSequence = $PhaseSequence -or (-not $PhaseSequence -and -not $PhaseGraph)
$RunGraph = $PhaseGraph -or (-not $PhaseSequence -and -not $PhaseGraph)

# DFW project detection
$Manifest = Get-DfwManifest -Root $ProjectRoot
$ProjectName = if ($Manifest -and $Manifest.name) { $Manifest.name } else { Split-Path $ProjectRoot -Leaf }
$IsDfwProject = $null -ne $Manifest

# Auto-discover directories if none specified
if ($Directories.Count -eq 0) {
    if ($IsDfwProject) {
        # Scan DFW canonical content directories that exist on disk
        $Directories = $DfwContentDirs | Where-Object { Test-Path (Join-Path $ProjectRoot $_) }
        if ($Directories.Count -eq 0) {
            Write-Host "  Warning: No DFW content directories found on disk." -ForegroundColor Yellow
            $Directories = $DfwContentDirs  # Fall back to full list (will skip missing)
        }
    } else {
        # Non-DFW project: scan common directory names
        $Directories = $DfwContentDirs
        Write-Host ""
        Write-Host "  Warning: No .dfw/project.json found at $ProjectRoot" -ForegroundColor Yellow
        Write-Host "  Running in compatibility mode with default DFW directories." -ForegroundColor Yellow
    }
}

Write-Header "DFW RESYNC" "Major"
Write-Host ""
Write-Status "Project" "$ProjectName $(if ($IsDfwProject) { '(DFW project)' } else { '(not a DFW project)' })"
Write-Status "Project Root" $ProjectRoot
Write-Status "Directories" ($Directories -join ", ")
Write-Status "Graph output" $GraphOutputFile
Write-Status "Skip _ prefix" $SkipUnderscorePrefix
Write-Status "Mode" $(if ($DryRun) { "DRY RUN (no changes)" } else { "LIVE" }) $(if ($DryRun) { "Yellow" } else { "Green" })
if ($Force) { Write-Status "Force" "ON - Ignoring caches" "Yellow" }
Write-Status "Phases" "Sequence=$RunSequence, Graph=$RunGraph" "Cyan"
Write-Host ""

if ($RunSequence) { Invoke-PhaseSequence }
if ($RunGraph)    { Invoke-PhaseGraph   }

Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Blue
Write-Host "  $ProjectName - Resync completed at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host ("=" * 60) -ForegroundColor Blue
Write-Host ""
