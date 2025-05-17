# Implementation Plan for Ultimaker Connect API Integration

## Overview

This document outlines the plan for extending the current Home Assistant Ultimaker integration to support the Ultimaker Connect API, which provides cloud-based access to Ultimaker printers and clusters.

## Current Integration vs. Cloud API

### Current Integration
- Uses local API (`http://<printer_ip>/api/v1/`)
- Direct connection to printer
- Limited to printers on the local network
- Basic printer status and control

### Cloud API (Ultimaker Connect)
- Uses cloud API (`https://api.ultimaker.com/connect/v1/`)
- Requires authentication
- Can access printers remotely
- Supports printer clusters
- Advanced features (maintenance tracking, material management, etc.)

## Implementation Phases

### Phase 1: Authentication and Basic Connection

1. **Add OAuth2 Authentication**
   - Implement OAuth2 authentication flow
   - Store and manage authentication tokens
   - Add configuration options for API credentials

2. **Create Cloud API Client**
   - Implement a new API client class for the cloud API
   - Support both local and cloud API connections
   - Handle authentication and token refresh

3. **Update Configuration Schema**
   - Add new configuration options for cloud API
   - Allow selecting between local and cloud API
   - Support for API credentials

### Phase 2: Basic Cloud API Sensors

1. **Implement Cluster Sensors**
   - Add sensors for cluster status
   - Add sensors for printer status within clusters
   - Support multiple printers in a cluster

2. **Update Existing Sensors**
   - Modify existing sensors to work with both local and cloud API
   - Ensure backward compatibility

3. **Add Print Job Sensors**
   - Implement enhanced print job sensors using cloud API data
   - Add historical print job data

### Phase 3: Advanced Features

1. **Implement Printer Actions**
   - Add services for printer control (pause, resume, abort, etc.)
   - Support remote printer control

2. **Maintenance Tracking**
   - Add sensors for maintenance status
   - Implement maintenance notification system

3. **Material Management**
   - Add sensors for material status
   - Implement material management features

4. **Usage Statistics**
   - Add sensors for printer usage statistics
   - Implement historical usage data visualization

## Code Changes

### New Files to Create

1. **`api_client.py`**
   - Base API client class
   - Local API client subclass
   - Cloud API client subclass

2. **`config_flow.py`**
   - Implement config flow for UI-based configuration
   - Support OAuth2 authentication flow

3. **`const.py`**
   - Constants for the integration
   - API endpoints
   - Sensor types

4. **`services.py`**
   - Service definitions
   - Service handler functions

### Files to Modify

1. **`__init__.py`**
   - Update setup function to support both API types
   - Add service registration

2. **`sensor.py`**
   - Update sensor platform to support both API types
   - Add new sensor types for cloud API

3. **`manifest.json`**
   - Update version
   - Add new dependencies (e.g., OAuth2 libraries)
   - Add config_flow support

## Configuration Example

```yaml
# Example configuration.yaml entry for local API
ultimaker:
  api_type: local
  host: 192.168.1.100
  name: My Ultimaker
  scan_interval: 10

# Example configuration.yaml entry for cloud API
ultimaker:
  api_type: cloud
  username: your_username
  password: your_password  # Or use secrets.yaml
  cluster_id: your_cluster_id  # Optional, if not specified, will use first available cluster
  name: My Ultimaker Cluster
  scan_interval: 30
```

## UI Configuration Flow

1. User selects Ultimaker integration
2. User chooses between local and cloud API
3. For local API:
   - User enters printer IP address and name
4. For cloud API:
   - User is redirected to Ultimaker login page
   - After authentication, user is redirected back to Home Assistant
   - User selects cluster (if multiple available)
5. User selects sensors to enable
6. Integration is set up

## Testing Plan

1. **Unit Tests**
   - Test API client classes
   - Test sensor data processing
   - Test configuration validation

2. **Integration Tests**
   - Test with mock API responses
   - Test authentication flow
   - Test sensor updates

3. **Manual Testing**
   - Test with actual Ultimaker printers
   - Test with Ultimaker cloud account
   - Test various configuration scenarios

## Documentation Updates

1. **README.md**
   - Add information about cloud API support
   - Update configuration examples
   - Document new features

2. **info.md**
   - Update with cloud API information
   - Add screenshots of new features

3. **Code Documentation**
   - Add docstrings to all new classes and methods
   - Update existing docstrings as needed

## Future Enhancements

1. **Advanced Automation**
   - Trigger automations based on print job status
   - Automate maintenance tasks

2. **Material Tracking**
   - Track material usage
   - Notify when materials are low

3. **Print Queue Management**
   - Manage print queue from Home Assistant
   - Prioritize print jobs

4. **Multi-User Support**
   - Support multiple user accounts
   - User-specific print job tracking

## Conclusion

This implementation plan provides a roadmap for extending the current Home Assistant Ultimaker integration to support the Ultimaker Connect API. By following this plan, the integration will gain powerful new features while maintaining compatibility with existing setups.