# PowerShell script for managing staging environment on Windows
# Usage: .\staging.ps1 [command]
# Commands: init, up, down, restart, logs, ps, migrate, seed, clean

param(
    [Parameter(Position=0)]
    [string]$Command = "help"
)

$ComposeFile = "docker-compose.staging.yml"
$EnvFile = ".env.staging"

# Check if docker is available
function Test-Docker {
    try {
        $null = Get-Command docker -ErrorAction Stop
        return $true
    } catch {
        Write-Host "Error: Docker not found in PATH!" -ForegroundColor Red
        Write-Host ""
        Write-Host "Please ensure Docker Desktop is installed and running." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Solutions:" -ForegroundColor Cyan
        Write-Host "  1. Restart PowerShell (Docker may need PATH refresh)"
        Write-Host "  2. Start Docker Desktop application"
        Write-Host "  3. Add Docker to PATH manually:"
        Write-Host '     $env:Path += ";C:\Program Files\Docker\Docker\resources\bin"'
        Write-Host ""
        return $false
    }
}

# Check Docker before running commands
if ($Command -ne "help") {
    if (-not (Test-Docker)) {
        exit 1
    }
}

function Show-Help {
    Write-Host "Staging Environment Manager" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage: .\staging.ps1 [command]" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Commands:" -ForegroundColor Green
    Write-Host "  init          - Initialize staging (up + migrate + seed)"
    Write-Host "  up            - Start staging environment"
    Write-Host "  down          - Stop staging environment"
    Write-Host "  restart       - Restart staging environment"
    Write-Host "  rebuild       - Rebuild staging environment"
    Write-Host "  logs          - Show all logs"
    Write-Host "  logs-media    - Show MediaBot logs"
    Write-Host "  logs-ai       - Show AIBot logs"
    Write-Host "  logs-db       - Show PostgreSQL logs"
    Write-Host "  ps            - Show containers status"
    Write-Host "  migrate       - Apply migrations"
    Write-Host "  seed          - Seed database with test data"
    Write-Host "  shell-media   - Open bash in MediaBot container"
    Write-Host "  shell-ai      - Open bash in AIBot container"
    Write-Host "  shell-db      - Open PostgreSQL shell"
    Write-Host "  clean         - Remove all containers and volumes"
    Write-Host ""
}

switch ($Command.ToLower()) {
    "init" {
        Write-Host "Initializing staging environment..." -ForegroundColor Cyan
        docker compose -f $ComposeFile --env-file $EnvFile up -d --build

        Write-Host "Waiting for database to be ready..." -ForegroundColor Yellow
        Start-Sleep -Seconds 10

        Write-Host "Applying migrations..." -ForegroundColor Cyan
        docker exec -it footagehub-staging-media-bot alembic upgrade head

        Write-Host "Seeding database..." -ForegroundColor Cyan
        docker exec -it footagehub-staging-media-bot python scripts/setup_staging_db.py

        Write-Host ""
        Write-Host "✅ Staging environment initialized!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Next steps:" -ForegroundColor Yellow
        Write-Host "  1. Check logs: .\staging.ps1 logs"
        Write-Host "  2. Check status: .\staging.ps1 ps"
        Write-Host "  3. Follow STAGING_TEST_PLAN.md for testing"
    }

    "up" {
        Write-Host "Starting staging environment..." -ForegroundColor Cyan
        docker compose -f $ComposeFile --env-file $EnvFile up -d --build
    }

    "down" {
        Write-Host "Stopping staging environment..." -ForegroundColor Cyan
        docker compose -f $ComposeFile down
    }

    "restart" {
        Write-Host "Restarting staging environment..." -ForegroundColor Cyan
        docker compose -f $ComposeFile restart
    }

    "rebuild" {
        Write-Host "Rebuilding staging environment..." -ForegroundColor Cyan
        docker compose -f $ComposeFile down
        docker compose -f $ComposeFile --env-file $EnvFile up -d --build
    }

    "logs" {
        Write-Host "Showing staging logs (Ctrl+C to exit)..." -ForegroundColor Cyan
        docker compose -f $ComposeFile logs -f
    }

    "logs-media" {
        Write-Host "Showing MediaBot logs..." -ForegroundColor Cyan
        docker compose -f $ComposeFile logs -f media-bot
    }

    "logs-ai" {
        Write-Host "Showing AIBot logs..." -ForegroundColor Cyan
        docker compose -f $ComposeFile logs -f ai-bot
    }

    "logs-db" {
        Write-Host "Showing PostgreSQL logs..." -ForegroundColor Cyan
        docker compose -f $ComposeFile logs -f postgres
    }

    "ps" {
        Write-Host "Staging containers status:" -ForegroundColor Cyan
        docker compose -f $ComposeFile ps
    }

    "migrate" {
        Write-Host "Applying migrations to staging database..." -ForegroundColor Cyan
        docker exec -it footagehub-staging-media-bot alembic upgrade head
    }

    "seed" {
        Write-Host "Seeding staging database with test data..." -ForegroundColor Cyan
        docker exec -it footagehub-staging-media-bot python scripts/setup_staging_db.py
    }

    "shell-media" {
        Write-Host "Opening shell in MediaBot staging container..." -ForegroundColor Cyan
        docker exec -it footagehub-staging-media-bot bash
    }

    "shell-ai" {
        Write-Host "Opening shell in AIBot staging container..." -ForegroundColor Cyan
        docker exec -it footagehub-staging-ai-bot bash
    }

    "shell-db" {
        Write-Host "Opening PostgreSQL shell in staging database..." -ForegroundColor Cyan
        docker exec -it footagehub-staging-db psql -U postgres -d footagehub_staging
    }

    "clean" {
        Write-Host "WARNING: This will remove all staging containers and volumes!" -ForegroundColor Red
        $confirm = Read-Host "Are you sure? [y/N]"
        if ($confirm -eq 'y' -or $confirm -eq 'Y') {
            docker compose -f $ComposeFile down -v
            Write-Host "Staging environment cleaned!" -ForegroundColor Green
        } else {
            Write-Host "Aborted." -ForegroundColor Yellow
        }
    }

    default {
        Show-Help
    }
}
