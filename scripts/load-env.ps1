Get-Content .env | Where-Object { $_ -match '^\s*[^#]\S*=' } | ForEach-Object {
    $key, $value = $_ -split '=', 2
    [System.Environment]::SetEnvironmentVariable($key.Trim(), $value.Trim(), 'Process')
}
