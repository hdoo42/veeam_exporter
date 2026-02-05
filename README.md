# Veeam Backup & Replication Prometheus Exporter

A Prometheus exporter that collects metrics from **Veeam Backup & Replication (VBR) Server** via its REST API.

> ⚠️ **Prerequisites**: This exporter connects directly to the Veeam VBR REST API (port 9419). If you have **Veeam Enterprise Manager** installed, consider using the [more detailed Veeam exporter](https://github.com/peekjef72/httpapi_exporter/blob/main/contribs/veeam/README.md) instead.

## Architecture

```
┌─────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   Prometheus    │────▶│   httpapi_exporter  │────▶│  Veeam Backup &     │
│                 │     │  + This Config      │     │  Replication Server │
└─────────────────┘     └─────────────────────┘     │   (REST API: 9419)  │
                                                    └─────────────────────┘
```

## Requirements

- **Veeam Backup & Replication v11 or later** with REST API enabled (port 9419)
- API credentials with `View` permissions for backups, jobs, servers, etc.
- [httpapi_exporter](https://github.com/ksy4228/httpapi_exporter) binary

## Quick Start

### 1. Download httpapi_exporter

```bash
# Download from releases page
wget https://github.com/ksy4228/httpapi_exporter/releases/download/v0.4.2/httpapi_exporter-linux-amd64
chmod +x httpapi_exporter
```

### 2. Set Environment Variables

```bash
# ✅ REQUIRED: Change these to your Veeam credentials
export VEEAM_USER="your_veeam_username"
export VEEAM_PASSWORD="your_veeam_password"
```

### 3. Configure and Run

See [Configuration Guide](#configuration-guide) below for detailed setup, then run:

```bash
# Option A: Specify target via command line (simplest for testing)
./httpapi_exporter -c config.yml -t your-veeam-server.example.com

# Option B: If you configured targets/example_target.yml, just run:
./httpapi_exporter -c config.yml

# Option C: Dry-run (test without starting server)
./httpapi_exporter -c config.yml -n -t your-veeam-server.example.com
```

## Configuration Guide

### Files You Need to Modify

#### 1. Environment Variables

| Variable | Description |
|----------|-------------|
| `VEEAM_USER` | Your Veeam username |
| `VEEAM_PASSWORD` | Your Veeam password |

#### 2. Target Configuration (Optional - for permanent targets)

If you want to pre-configure targets instead of using `-t` flag, edit `targets/example_target.yml`:

```yaml
# MODIFY THIS SECTION
- name: my-veeam-server              # Any name you want
  scheme: https
  host: my-veeam-server.company.com  # <-- Your Veeam server FQDN or IP
  port: 9419                         # REST API port (usually 9419)
  auth_name: default
  profile: veeam_backup
  collectors:
    - ~.*_metrics
```

> 💡 **Tip**: For quick testing, skip this file and use `-t your-server` flag instead.

#### 3. SSL Verification (If Needed)

If your Veeam server uses **self-signed certificates**, you may need to disable SSL verification in `config.yml`:

```yaml
- name: default headers and settings
  set_fact:
    # ... other settings ...
    verifySSL: false
```

### Files You Don't Need to Modify

| File | Description |
|------|-------------|
| `config.yml` (auth/global sections) | Default authentication and global settings work out of the box |
| `metrics/*.collector.yml` | Metric collection logic - no changes needed unless customizing |

## Collected Metrics

### Overview

| Category | Metrics | Description |
|----------|---------|-------------|
| **Backups** | `veeam_backup_backups_total`, `veeam_backup_backups_by_platform` | Total backups and breakdown by platform (VMware, Hyper-V, etc.) |
| **Jobs** | `veeam_backup_jobs_total`, `veeam_backup_jobs_enabled`, `veeam_backup_jobs_disabled` | Backup job statistics |
| **Infrastructure** | Servers, Proxies, Repositories | Infrastructure component counts and status |
| **Sessions** | `veeam_backup_sessions_total`, `veeam_backup_sessions_by_result` | Job session history (Success/Failed) |
| **Health** | `veeam_backup_up`, `veeam_backup_collector_status` | Exporter and API health |

### Detailed Metrics

#### Backups

```
# Total backup count
veeam_backup_backups_total 3

# By platform (label: platform=vmware,hyperv,windows_physical,linux_physical,vcd,nas,tape)
veeam_backup_backups_by_platform{platform="vmware"} 3
veeam_backup_backups_by_platform{platform="hyperv"} 0
```

#### Jobs

```
veeam_backup_jobs_total 3
veeam_backup_jobs_enabled 3
veeam_backup_jobs_disabled 0
```

#### Sessions

```
veeam_backup_sessions_total 200
veeam_backup_sessions_by_result{result="Success"} 189
veeam_backup_sessions_by_result{result="Failed"} 11
```

#### Infrastructure

```
# Managed Servers
veeam_backup_managed_servers_total 2
veeam_backup_managed_servers_by_type{type="vmware"} 1
veeam_backup_managed_servers_by_type{type="windows"} 1

# Proxies
veeam_backup_proxies_total 1
veeam_backup_proxies_max_tasks_total 2

# Repositories
veeam_backup_repositories_total 2
veeam_backup_repositories_by_type{type="WinLocal"} 2
```

## Prometheus Configuration

Add to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'veeam_backup'
    static_configs:
      - targets: ['your-veeam-server.company.com']  # ✅ CHANGE THIS
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: localhost:9101  # Exporter address (change if different)
```

## REST API Reference

### Built-in API Documentation (Swagger UI)

Veeam v11+ includes a **Swagger UI** for exploring the REST API:

```
https://your-veeam-server:9419/swagger/ui
```

This is useful for:
- Understanding available endpoints
- Testing API calls directly in browser
- Exploring response schemas

### Used Endpoints

| Purpose | Endpoint |
|---------|----------|
| Authentication | `POST /oauth2/token` |
| Server Info | `GET /api/v1/serverCertificate` |
| Backups | `GET /api/v1/backups` |
| Jobs | `GET /api/v1/jobs` |
| Managed Servers | `GET /api/v1/backupInfrastructure/managedServers` |
| Proxies | `GET /api/v1/backupInfrastructure/proxies` |
| Repositories | `GET /api/v1/backupInfrastructure/repositories` |
| Sessions | `GET /api/v1/sessions` |

## Troubleshooting

### Connection Issues

```bash
# Test connectivity to Veeam REST API
curl -k -u "username:password" \
  "https://your-veeam-server:9419/api/v1/serverTime"
```

### Authentication Failures

Check `veeam_backup_collector_status` metric:
- `0` = Error
- `1` = OK ✅
- `2` = Invalid login (check credentials)
- `3` = Timeout

## Alternatives

### Veeam Enterprise Manager Exporter

If you have **Veeam Enterprise Manager** deployed, you can get more detailed metrics:

👉 [Veeam Enterprise Manager Exporter](https://github.com/peekjef72/httpapi_exporter/blob/main/contribs/veeam/README.md)

**Comparison:**

| Feature | This Exporter (VBR Direct) | Enterprise Manager Exporter |
|---------|---------------------------|----------------------------|
| **Target** | Veeam VBR Server | Veeam Enterprise Manager |
| **API Port** | 9419 | 9398 |
| **Metrics Detail** | Basic counts and status | More detailed job metrics, tenant info |
| **Multi-Server** | Per-server connection | Centralized multi-server view |
| **Required License** | Any VBR license | Enterprise Manager license |

Choose based on your infrastructure:
- **This exporter**: Simple, direct connection to single/multiple VBR servers
- **EM Exporter**: More metrics, centralized management, multi-tenancy support

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built on [httpapi_exporter](https://github.com/ksy4228/httpapi_exporter) by @ksy4228
- Uses Veeam Backup & Replication REST API (v11+)
