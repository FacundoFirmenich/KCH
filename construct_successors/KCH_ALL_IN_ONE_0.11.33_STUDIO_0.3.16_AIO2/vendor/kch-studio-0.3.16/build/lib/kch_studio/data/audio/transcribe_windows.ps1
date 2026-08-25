param(
    [Parameter(Mandatory=$true)][string]$InputWav,
    [Parameter(Mandatory=$true)][string]$OutputJson,
    [string]$Culture = "es-ES"
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech
$cultureInfo = [System.Globalization.CultureInfo]::GetCultureInfo($Culture)
$recognizerInfo = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() |
    Where-Object { $_.Culture.Name -eq $Culture } |
    Select-Object -First 1
if ($null -eq $recognizerInfo) { throw "No installed System.Speech recognizer for $Culture" }
$engine = [System.Speech.Recognition.SpeechRecognitionEngine]::new($recognizerInfo)
try {
    $engine.LoadGrammar([System.Speech.Recognition.DictationGrammar]::new())
    $engine.SetInputToWaveFile((Resolve-Path -LiteralPath $InputWav))
    $segments = [System.Collections.Generic.List[object]]::new()
    while ($true) {
        $result = $engine.Recognize()
        if ($null -eq $result) { break }
        $segments.Add([ordered]@{
            text = $result.Text
            confidence = [double]$result.Confidence
            audio_position_seconds = [double]$result.Audio.AudioPosition.TotalSeconds
            duration_seconds = [double]$result.Audio.Duration.TotalSeconds
        })
    }
    $payload = [ordered]@{
        schema = "kch.windows-system-speech-transcript.v0.1.0"
        culture = $Culture
        backend = "WINDOWS_SYSTEM_SPEECH"
        segments = $segments
        text = (($segments | ForEach-Object { $_.text }) -join " ")
    }
    $payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputJson -Encoding UTF8
} finally {
    $engine.Dispose()
}
