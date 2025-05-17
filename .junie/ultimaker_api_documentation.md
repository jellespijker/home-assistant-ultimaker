# Ultimaker Connect API Documentation

## Overview
The Stardust Cura Connect API offers a REST interface to reach Cura Connect clusters functionality via the cloud.

- **Base URL**: `/connect/v1`
- **API Specification URL**: https://api.ultimaker.com/connect/v1/spec

## Endpoints

### General Endpoints
- `GET /` - Get API uptime
- `GET /spec` - Get API specification
- `GET /teapot` - Easter egg endpoint (HTTP 418 I'm a teapot)

### Cluster Management
- `GET /clusters` - Get all clusters
- `POST /clusters` - Check clusters access
- `GET /clusters/{cluster_id}` - Get specific cluster
- `DELETE /clusters/{cluster_id}` - Delete a cluster
- `POST /clusters/{cluster_id}/note` - Update cluster note
- `POST /clusters/{cluster_id}/share` - Share a cluster
- `POST /clusters/share_all` - Share all clusters
- `GET /clusters/team_count` - Count clusters for teams

### Cluster Status and Actions
- `GET /clusters/{cluster_id}/status` - Get cluster status
- `GET /clusters/{cluster_id}/action_status/{action_id}` - Get action status
- `POST /clusters/{cluster_id}/printers/{cluster_printer_id}/action/{action}` - Perform printer action

### Print Jobs
- `GET /print_jobs` - Get all print jobs
- `GET /print_jobs/reports` - Get print job instances
- `GET /clusters/{cluster_id}/print_jobs/{cluster_job_id}` - Get print job details
- `POST /clusters/{cluster_id}/print_jobs/{cluster_job_id}` - Update print job instance
- `POST /clusters/{cluster_id}/print_jobs/{cluster_job_id}/action/{action}` - Perform print job action
- `POST /clusters/{cluster_id}/print/{job_id}` - Submit print request
- `POST /clusters/{cluster_id}/reprint/{original_cluster_id}/{job_instance_uuid}` - Reprint request
- `GET /filters/print_jobs` - Get print job filters

### Maintenance
- `PUT /clusters/{cluster_id}/maintenance` - Add maintenance task log
- `GET /clusters/{cluster_id}/maintenance/completed` - Get completed maintenance tasks
- `GET /clusters/{cluster_id}/maintenance/pending` - Get pending maintenance tasks

### Registration
- `POST /confirm-registration/{connection_id}` - Confirm registration
- `POST /confirm-registration-pin/{pin_code}` - Confirm registration with PIN code

### MakerBot Integration
- `GET /makerbot/printers` - Get MakerBot printers
- `PUT /makerbot/printers` - Confirm MakerBot registration

### Materials
- `PUT /materials/upload` - Upload material profile

### Settings and Usage
- `GET /settings` - Get current organization settings
- `POST /settings` - Update current organization settings
- `GET /usage` - Get printer usage
- `GET /user/{user_id}/clusters` - Get user clusters

## Models

The API uses numerous models for data exchange. Some of the key models include:

- `ClusterResponse` - Information about a cluster
- `ClusterStatusResponse` - Status information for a cluster
- `PrintJobResponse` - Information about a print job
- `PrintJobDetailsResponse` - Detailed information about a print job
- `ClusterPrinterStatus` - Status information for a printer in a cluster
- `ActionStatusResponse` - Status of an action performed on a cluster
- `PrinterMaintenanceTaskResponse` - Information about a maintenance task

## Authentication

Most endpoints require authentication, which is handled through OAuth2. The API uses bearer tokens for authorization.

## Integration Opportunities

Compared to the current Home Assistant integration which uses the local printer API, this cloud API offers additional functionality:

1. **Cluster Management** - Manage multiple printers in a cluster
2. **Remote Control** - Control printers remotely through the cloud
3. **Print Job Management** - More detailed print job management
4. **Maintenance Tracking** - Track and manage printer maintenance
5. **Material Management** - Upload and manage material profiles
6. **Usage Statistics** - Track printer usage statistics

## Implementation Considerations

When extending the current integration to use this API:

1. **Authentication** - Need to implement OAuth2 authentication
2. **Cloud vs. Local** - Consider offering both local and cloud API options
3. **New Sensors** - Add new sensors for cluster status, maintenance, etc.
4. **Services** - Add services for printer actions, print job management, etc.
5. **Configuration** - Update configuration to support cloud API credentials