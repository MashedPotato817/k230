param(
    [string]$DatasetRoot = (Join-Path $PSScriptRoot 'dataset')
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Get-ImageSize([IO.FileInfo]$ImageFile) {
    $bytes = [IO.File]::ReadAllBytes($ImageFile.FullName)
    if ($bytes.Length -ge 24 -and ($bytes[0..7] -join ',') -eq '137,80,78,71,13,10,26,10') {
        $width = (([int]$bytes[16]) -shl 24) -bor (([int]$bytes[17]) -shl 16) -bor (([int]$bytes[18]) -shl 8) -bor $bytes[19]
        $height = (([int]$bytes[20]) -shl 24) -bor (([int]$bytes[21]) -shl 16) -bor (([int]$bytes[22]) -shl 8) -bor $bytes[23]
        return @($width, $height)
    }
    if ($bytes.Length -ge 30 -and [Text.Encoding]::ASCII.GetString($bytes, 0, 4) -eq 'RIFF' -and [Text.Encoding]::ASCII.GetString($bytes, 8, 4) -eq 'WEBP') {
        $kind = [Text.Encoding]::ASCII.GetString($bytes, 12, 4)
        if ($kind -eq 'VP8 ') {
            return @((([int]$bytes[26]) -bor (([int]$bytes[27]) -shl 8)) -band 0x3fff, (([int]$bytes[28]) -bor (([int]$bytes[29]) -shl 8)) -band 0x3fff)
        }
        if ($kind -eq 'VP8X') {
            return @(1 + ([int]$bytes[24] -bor (([int]$bytes[25]) -shl 8) -bor (([int]$bytes[26]) -shl 16)), 1 + ([int]$bytes[27] -bor (([int]$bytes[28]) -shl 8) -bor (([int]$bytes[29]) -shl 16)))
        }
        if ($kind -eq 'VP8L') {
            return @(1 + ([int]$bytes[21] -bor (([int]$bytes[22] -band 0x3f) -shl 8)), 1 + (([int]$bytes[22] -shr 6) -bor (([int]$bytes[23]) -shl 2) -bor (([int]$bytes[24] -band 0x0f) -shl 10)))
        }
    }
    if ($bytes.Length -ge 4 -and $bytes[0] -eq 255 -and $bytes[1] -eq 216) {
        $position = 2
        while ($position -lt ($bytes.Length - 9)) {
            while ($position -lt $bytes.Length -and $bytes[$position] -eq 255) { $position++ }
            $marker = $bytes[$position]; $position++
            if ($marker -in 216,217 -or ($marker -ge 208 -and $marker -le 215)) { continue }
            $length = (([int]$bytes[$position]) -shl 8) -bor $bytes[$position + 1]
            if ($length -lt 2 -or ($position + $length) -gt $bytes.Length) { break }
            if ($marker -in 192,193,194,195,197,198,199,201,202,203,205,206,207) {
                $width = (([int]$bytes[$position + 5]) -shl 8) -bor $bytes[$position + 6]
                $height = (([int]$bytes[$position + 3]) -shl 8) -bor $bytes[$position + 4]
                return @($width, $height)
            }
            $position += $length
        }
    }
    throw "无法读取图像尺寸：$($ImageFile.FullName)"
}

function Write-VocXml([string]$Path, [string]$Filename, [int]$Width, [int]$Height, [array]$Boxes) {
    $settings = [Xml.XmlWriterSettings]::new(); $settings.Indent = $true; $settings.Encoding = [Text.UTF8Encoding]::new($false)
    $writer = [Xml.XmlWriter]::Create($Path, $settings)
    try {
        $writer.WriteStartDocument(); $writer.WriteStartElement('annotation'); $writer.WriteElementString('filename', $Filename)
        $writer.WriteStartElement('size'); $writer.WriteElementString('width', $Width); $writer.WriteElementString('height', $Height); $writer.WriteElementString('depth', '3'); $writer.WriteEndElement()
        $writer.WriteElementString('segmented', '0')
        foreach ($box in $Boxes) {
            $writer.WriteStartElement('object'); $writer.WriteElementString('name', 'gangqiu'); $writer.WriteElementString('truncated', '0'); $writer.WriteElementString('difficult', '0')
            $writer.WriteStartElement('bndbox'); $writer.WriteElementString('xmin', $box.xmin); $writer.WriteElementString('ymin', $box.ymin); $writer.WriteElementString('xmax', $box.xmax); $writer.WriteElementString('ymax', $box.ymax); $writer.WriteEndElement(); $writer.WriteEndElement()
        }
        $writer.WriteEndElement(); $writer.WriteEndDocument()
    }
    finally { $writer.Dispose() }
}

function Initialize-Output([string]$Name) {
    $output = Join-Path $DatasetRoot $Name
    $archive = "$output.zip"
    if ((Test-Path -LiteralPath $output) -or (Test-Path -LiteralPath $archive)) { throw "输出已存在：$output 或 $archive" }
    [IO.Directory]::CreateDirectory((Join-Path $output 'images')) | Out-Null
    [IO.Directory]::CreateDirectory((Join-Path $output 'xml')) | Out-Null
    [IO.File]::WriteAllText((Join-Path $output 'labels.txt'), "gangqiu`n", [Text.UTF8Encoding]::new($false))
    return $output
}

function Add-Xzh([string]$Source, [string]$Output) {
    $images = @(Get-ChildItem (Join-Path $Source 'images') -File | Sort-Object Name)
    $totalBoxes = 0
    for ($i = 0; $i -lt $images.Count; $i++) {
        $image = $images[$i]; $label = Join-Path $Source "labels/$($image.BaseName).txt"
        if (-not (Test-Path -LiteralPath $label)) { throw "缺少标注：$label" }
        $size = Get-ImageSize $image; $boxes = @()
        foreach ($line in Get-Content -LiteralPath $label) {
            $parts = $line.Trim() -split '\s+'
            if ($parts.Count -ne 5 -or $parts[0] -ne '0') { throw "无效 YOLO 标注：$label" }
            $cx=[double]$parts[1]; $cy=[double]$parts[2]; $bw=[double]$parts[3]; $bh=[double]$parts[4]
            $xmin=[Math]::Max(0, [Math]::Floor(($cx-$bw/2)*$size[0])); $ymin=[Math]::Max(0, [Math]::Floor(($cy-$bh/2)*$size[1]))
            $xmax=[Math]::Min($size[0], [Math]::Ceiling(($cx+$bw/2)*$size[0])); $ymax=[Math]::Min($size[1], [Math]::Ceiling(($cy+$bh/2)*$size[1]))
            if ($xmax -le $xmin -or $ymax -le $ymin) { throw "无效边界框：$label" }
            $boxes += [pscustomobject]@{xmin=$xmin;ymin=$ymin;xmax=$xmax;ymax=$ymax}
        }
        $stem = 'xzh_{0:D4}' -f ($i + 1); $filename = "$stem$($image.Extension)"
        Copy-Item -LiteralPath $image.FullName -Destination (Join-Path $Output "images/$filename")
        Write-VocXml (Join-Path $Output "xml/$stem.xml") $filename $size[0] $size[1] $boxes
        $totalBoxes += $boxes.Count
    }
    return [pscustomobject]@{dataset='xzh';images=$images.Count;boxes=$totalBoxes}
}

function Add-Ywq([string]$Source, [string]$Output) {
    $images = @(Get-ChildItem (Join-Path $Source 'images') -File | Sort-Object Name)
    $totalBoxes = 0
    for ($i = 0; $i -lt $images.Count; $i++) {
        $image=$images[$i]; $sourceXml=Join-Path $Source "xml/$($image.BaseName).xml"
        if (-not (Test-Path -LiteralPath $sourceXml)) { throw "缺少标注：$sourceXml" }
        [xml]$inputXml = Get-Content -Raw -LiteralPath $sourceXml; $boxes=@()
        foreach ($object in @($inputXml.annotation.object)) {
            $box=$object.bndbox
            if ($null -eq $box) { throw "缺少边界框：$sourceXml" }
            $boxes += [pscustomobject]@{xmin=[int]$box.xmin;ymin=[int]$box.ymin;xmax=[int]$box.xmax;ymax=[int]$box.ymax}
        }
        $size=Get-ImageSize $image; $stem='ywq_{0:D4}' -f ($i+1); $filename="$stem$($image.Extension)"
        Copy-Item -LiteralPath $image.FullName -Destination (Join-Path $Output "images/$filename")
        Write-VocXml (Join-Path $Output "xml/$stem.xml") $filename $size[0] $size[1] $boxes
        $totalBoxes += $boxes.Count
    }
    return [pscustomobject]@{dataset='ywq';images=$images.Count;boxes=$totalBoxes}
}

$xzhOutput=Initialize-Output 'dataset_xzh_upload'; $xzhStats=Add-Xzh (Join-Path $DatasetRoot 'dataset_xzh') $xzhOutput
$ywqOutput=Initialize-Output 'dataset_ywq_upload'; $ywqStats=Add-Ywq (Join-Path $DatasetRoot 'dataset_ywq') $ywqOutput
[IO.Compression.ZipFile]::CreateFromDirectory($xzhOutput, "$xzhOutput.zip", [IO.Compression.CompressionLevel]::Optimal, $false)
[IO.Compression.ZipFile]::CreateFromDirectory($ywqOutput, "$ywqOutput.zip", [IO.Compression.CompressionLevel]::Optimal, $false)
$xzhStats; $ywqStats
