param(
    [string]$SourceRoot = (Join-Path $PSScriptRoot 'dataset'),
    [string]$OutputRoot = (Join-Path $PSScriptRoot 'dataset')
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Get-ZipEntries([string]$ZipPath) {
    $zip = [IO.Compression.ZipFile]::OpenRead($ZipPath)
    $result = @{}
    foreach ($entry in $zip.Entries) {
        if (-not $entry.FullName.EndsWith('/')) { $result[$entry.FullName] = $entry }
    }
    return [pscustomobject]@{ Archive=$zip; Entries=$result }
}

function Read-ZipText($entry) {
    $reader = [IO.StreamReader]::new($entry.Open())
    try { return $reader.ReadToEnd() }
    finally { $reader.Dispose() }
}

function Copy-ZipEntry($entry, [string]$Destination) {
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Destination)) | Out-Null
    $input = $entry.Open()
    try {
        $output = [IO.File]::Create($Destination)
        try { $input.CopyTo($output) }
        finally { $output.Dispose() }
    }
    finally { $input.Dispose() }
}

function Get-ImageSize($entry) {
    $stream = $entry.Open()
    try {
        $buffer = [IO.MemoryStream]::new()
        try {
            $stream.CopyTo($buffer); $bytes = $buffer.ToArray()
            if ($bytes.Length -ge 24 -and $bytes[0..7] -join ',' -eq '137,80,78,71,13,10,26,10') {
                $width = (([int]$bytes[16]) -shl 24) -bor (([int]$bytes[17]) -shl 16) -bor (([int]$bytes[18]) -shl 8) -bor $bytes[19]
                $height = (([int]$bytes[20]) -shl 24) -bor (([int]$bytes[21]) -shl 16) -bor (([int]$bytes[22]) -shl 8) -bor $bytes[23]
                return @($width, $height, '3')
            }
            if ($bytes.Length -ge 4 -and $bytes[0] -eq 255 -and $bytes[1] -eq 216) {
                $pos = 2
                while ($pos -lt ($bytes.Length - 9)) {
                    while ($pos -lt $bytes.Length -and $bytes[$pos] -eq 255) { $pos++ }
                    $marker = $bytes[$pos]; $pos++
                    if ($marker -in 216,217 -or ($marker -ge 208 -and $marker -le 215)) { continue }
                    $length = (([int]$bytes[$pos]) -shl 8) -bor $bytes[$pos + 1]
                    if ($length -lt 2 -or $pos + $length -gt $bytes.Length) { break }
                    if ($marker -in 192,193,194,195,197,198,199,201,202,203,205,206,207) {
                        $height = (([int]$bytes[$pos + 3]) -shl 8) -bor $bytes[$pos + 4]
                        $width = (([int]$bytes[$pos + 5]) -shl 8) -bor $bytes[$pos + 6]
                        return @($width, $height, '3')
                    }
                    $pos += $length
                }
            }
            throw "无法读取图像尺寸：$($entry.FullName)"
        }
        finally { $buffer.Dispose() }
    }
    finally { $stream.Dispose() }
}

function New-VocXml([string]$Filename, [int]$Width, [int]$Height, [string]$Depth, [array]$Boxes) {
    $settings = [Xml.XmlWriterSettings]::new()
    $settings.Indent = $true
    $settings.Encoding = [Text.UTF8Encoding]::new($false)
    $builder = [Text.StringBuilder]::new()
    $writer = [Xml.XmlWriter]::Create($builder, $settings)
    $writer.WriteStartDocument()
    $writer.WriteStartElement('annotation')
    $writer.WriteElementString('filename', $Filename)
    $writer.WriteStartElement('size')
    $writer.WriteElementString('width', $Width)
    $writer.WriteElementString('height', $Height)
    $writer.WriteElementString('depth', $Depth)
    $writer.WriteEndElement()
    $writer.WriteElementString('segmented', '0')
    foreach ($box in $Boxes) {
        $writer.WriteStartElement('object')
        $writer.WriteElementString('name', 'gangqiu')
        $writer.WriteElementString('truncated', '0')
        $writer.WriteElementString('difficult', '0')
        $writer.WriteStartElement('bndbox')
        $writer.WriteElementString('xmin', $box.xmin)
        $writer.WriteElementString('ymin', $box.ymin)
        $writer.WriteElementString('xmax', $box.xmax)
        $writer.WriteElementString('ymax', $box.ymax)
        $writer.WriteEndElement(); $writer.WriteEndElement()
    }
    $writer.WriteEndElement(); $writer.WriteEndDocument(); $writer.Dispose()
    return $builder.ToString()
}

function New-Staging([string]$Name) {
    $path = Join-Path $OutputRoot $Name
    if (Test-Path -LiteralPath $path) { throw "输出目录已存在：$path" }
    [IO.Directory]::CreateDirectory((Join-Path $path 'images')) | Out-Null
    [IO.Directory]::CreateDirectory((Join-Path $path 'xml')) | Out-Null
    [IO.File]::WriteAllText((Join-Path $path 'labels.txt'), "gangqiu`n", [Text.UTF8Encoding]::new($false))
    return $path
}

function Compress-Staging([string]$Staging, [string]$ZipName) {
    $zipPath = Join-Path $OutputRoot $ZipName
    if (Test-Path -LiteralPath $zipPath) { throw "输出文件已存在：$zipPath" }
    [IO.Compression.ZipFile]::CreateFromDirectory($Staging, $zipPath, [IO.Compression.CompressionLevel]::Optimal, $false)
    return $zipPath
}

$stats = @()

# xzh: YOLO normalized labels -> Pascal VOC XML.
$xzhZipSource = Get-ZipEntries (Join-Path $SourceRoot 'dataset_xzh.zip')
$xzhEntries = $xzhZipSource.Entries
$xzhImages = $xzhEntries.Keys | Where-Object { $_ -match '^dataset/images/.+\.(jpg|jpeg|png)$' }
$xzhLabels = $xzhEntries.Keys | Where-Object { $_ -match '^dataset/labels/.+\.txt$' }
$xzhStage = New-Staging 'dataset_xzh_voc'
$xzhIncluded = 0; $xzhMissingLabel = 0; $xzhInvalid = 0
foreach ($imagePath in $xzhImages) {
    $file = [IO.Path]::GetFileName($imagePath); $stem = [IO.Path]::GetFileNameWithoutExtension($file)
    $labelPath = "dataset/labels/$stem.txt"
    if (-not $xzhEntries.ContainsKey($labelPath)) { $xzhMissingLabel++; continue }
    $size = Get-ImageSize $xzhEntries[$imagePath]; $boxes = @()
    foreach ($line in (Read-ZipText $xzhEntries[$labelPath]).Trim().Split("`n")) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $parts = $line.Trim() -split '\s+'
        if ($parts.Count -ne 5 -or $parts[0] -ne '0') { $xzhInvalid++; continue }
        $cx=[double]$parts[1]; $cy=[double]$parts[2]; $bw=[double]$parts[3]; $bh=[double]$parts[4]
        $xmin=[Math]::Max(0, [Math]::Floor(($cx-$bw/2)*$size[0])); $ymin=[Math]::Max(0, [Math]::Floor(($cy-$bh/2)*$size[1]))
        $xmax=[Math]::Min($size[0], [Math]::Ceiling(($cx+$bw/2)*$size[0])); $ymax=[Math]::Min($size[1], [Math]::Ceiling(($cy+$bh/2)*$size[1]))
        if ($xmax -le $xmin -or $ymax -le $ymin) { $xzhInvalid++; continue }
        $boxes += [pscustomobject]@{xmin=$xmin;ymin=$ymin;xmax=$xmax;ymax=$ymax}
    }
    Copy-ZipEntry $xzhEntries[$imagePath] (Join-Path $xzhStage "images/$file")
    [IO.File]::WriteAllText((Join-Path $xzhStage "xml/$stem.xml"), (New-VocXml $file $size[0] $size[1] '3' $boxes), [Text.UTF8Encoding]::new($false))
    $xzhIncluded++
}
$xzhOrphanLabels = @($xzhLabels | Where-Object { $stem=[IO.Path]::GetFileNameWithoutExtension($_); -not ($xzhImages | Where-Object {[IO.Path]::GetFileNameWithoutExtension($_) -eq $stem}) }).Count
$xzhZip = Compress-Staging $xzhStage 'dataset_xzh_voc.zip'
$xzhZipSource.Archive.Dispose()
$stats += [pscustomobject]@{dataset='xzh'; images=$xzhIncluded; skipped_images=$xzhMissingLabel; orphan_labels=$xzhOrphanLabels; invalid_boxes=$xzhInvalid; output=$xzhZip}

# ywq: existing VOC XML, relocate and standardize every class name.
$ywqZipSource = Get-ZipEntries (Join-Path $SourceRoot 'dataset_ywq.zip')
$ywqEntries = $ywqZipSource.Entries
$ywqImages = $ywqEntries.Keys | Where-Object { $_ -match '^images/.+\.(jpg|jpeg|png)$' }
$ywqXmls = $ywqEntries.Keys | Where-Object { $_ -match '^annotations/.+\.xml$' }
$ywqStage = New-Staging 'dataset_ywq_voc'
$ywqIncluded = 0; $ywqMissingXml = 0; $ywqInvalid = 0
foreach ($imagePath in $ywqImages) {
    $file = [IO.Path]::GetFileName($imagePath); $stem = [IO.Path]::GetFileNameWithoutExtension($file); $xmlPath="annotations/$stem.xml"
    if (-not $ywqEntries.ContainsKey($xmlPath)) { $ywqMissingXml++; continue }
    try { [xml]$xml = Read-ZipText $ywqEntries[$xmlPath] } catch { $ywqInvalid++; continue }
    $xml.annotation.filename = $file
    foreach ($object in @($xml.annotation.object)) { $object.name = 'gangqiu' }
    Copy-ZipEntry $ywqEntries[$imagePath] (Join-Path $ywqStage "images/$file")
    $xml.Save((Join-Path $ywqStage "xml/$stem.xml"))
    $ywqIncluded++
}
$ywqOrphanXml = @($ywqXmls | Where-Object { $stem=[IO.Path]::GetFileNameWithoutExtension($_); -not ($ywqImages | Where-Object {[IO.Path]::GetFileNameWithoutExtension($_) -eq $stem}) }).Count
$ywqZip = Compress-Staging $ywqStage 'dataset_ywq_voc.zip'
$ywqZipSource.Archive.Dispose()
$stats += [pscustomobject]@{dataset='ywq'; images=$ywqIncluded; skipped_images=$ywqMissingXml; orphan_labels=$ywqOrphanXml; invalid_boxes=$ywqInvalid; output=$ywqZip}

$stats | Format-Table -AutoSize
