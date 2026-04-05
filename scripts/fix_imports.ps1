# Fix imports: db.* -> shared.db.*

Write-Host "Fixing imports in media_bot..." -ForegroundColor Cyan

Get-ChildItem -Path ".\media_bot" -Recurse -Filter "*.py" | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $originalContent = $content

    # Replace imports
    $content = $content -replace 'from db\.', 'from shared.db.'
    $content = $content -replace 'from db import', 'from shared.db import'
    $content = $content -replace 'import db\.', 'import shared.db.'

    if ($content -ne $originalContent) {
        Set-Content -Path $_.FullName -Value $content -NoNewline
        Write-Host "  Fixed: $($_.FullName)" -ForegroundColor Green
    }
}

Write-Host "`nFixing imports in ai_bot..." -ForegroundColor Cyan

Get-ChildItem -Path ".\ai_bot" -Recurse -Filter "*.py" | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $originalContent = $content

    # Replace imports
    $content = $content -replace 'from db\.', 'from shared.db.'
    $content = $content -replace 'from db import', 'from shared.db import'
    $content = $content -replace 'import db\.', 'import shared.db.'

    if ($content -ne $originalContent) {
        Set-Content -Path $_.FullName -Value $content -NoNewline
        Write-Host "  Fixed: $($_.FullName)" -ForegroundColor Green
    }
}

Write-Host "`n✅ Import fixes complete!" -ForegroundColor Green
