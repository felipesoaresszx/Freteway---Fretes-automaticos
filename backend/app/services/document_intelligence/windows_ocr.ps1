param([Parameter(Mandatory=$true)][string]$ImagePath, [string]$OutputPath)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$awaitMethod = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1
function Await-Result($Operation, $ResultType) {
    $task = $awaitMethod.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    try { $task.Wait() } catch { throw $task.Exception.ToString() }
    $task.Result
}
$ImagePath = (Resolve-Path -LiteralPath $ImagePath).ProviderPath.Replace('/', '\')
$file = Await-Result ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) ([Windows.Storage.StorageFile])
$stream = Await-Result ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
try {
    $decoder = Await-Result ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await-Result ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if ($null -eq $engine) { throw 'OCR language is not installed' }
    $result = Await-Result ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $lines = @($result.Lines | ForEach-Object { @{text=$_.Text; words=@($_.Words | ForEach-Object { @{text=$_.Text; x=$_.BoundingRect.X; y=$_.BoundingRect.Y; width=$_.BoundingRect.Width; height=$_.BoundingRect.Height} })} })
    $json = ConvertTo-Json -InputObject $lines -Depth 5 -Compress
    if ($OutputPath) { [System.IO.File]::WriteAllText($OutputPath, $json, [System.Text.UTF8Encoding]::new($false)) } else { $json }
} finally { $stream.Dispose() }
