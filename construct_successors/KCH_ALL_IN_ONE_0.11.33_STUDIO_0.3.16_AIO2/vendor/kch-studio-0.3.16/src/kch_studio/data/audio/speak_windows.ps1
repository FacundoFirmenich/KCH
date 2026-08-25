param(
    [Parameter(Mandatory=$true)][string]$InputText,
    [string]$Culture = "es-ES"
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech
$text = [System.IO.File]::ReadAllText((Resolve-Path -LiteralPath $InputText), [System.Text.Encoding]::UTF8)
$synth = [System.Speech.Synthesis.SpeechSynthesizer]::new()
try {
    $voice = $synth.GetInstalledVoices() |
        Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -eq $Culture } |
        Select-Object -First 1
    if ($null -ne $voice) { $synth.SelectVoice($voice.VoiceInfo.Name) }
    $synth.Speak($text)
} finally {
    $synth.Dispose()
}
