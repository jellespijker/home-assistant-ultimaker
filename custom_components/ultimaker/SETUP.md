# Ultimaker Integration Setup Guide

This guide will help you set up the Ultimaker integration with Home Assistant, including authentication with Ultimaker's OpenID Connect (OIDC) service.

## Important Note

This integration **only supports configuration through the UI** (Devices & Services) and **does not support** configuration through YAML files (configuration.yaml). Please follow the UI-based setup instructions below.

## Prerequisites

- Home Assistant instance
- Ultimaker printer (for local API) or Ultimaker account (for cloud API)
- Client credentials from Ultimaker (for cloud API)

## Setup Options

The Ultimaker integration supports two connection methods:

1. **Local API** - Connect directly to your Ultimaker printer on your local network
2. **Cloud API** - Connect to your Ultimaker printer(s) through the Ultimaker Connect cloud service

## Local API Setup

1. In Home Assistant, go to **Settings** > **Devices & Services**
2. Click the **+ ADD INTEGRATION** button
3. Search for and select **Ultimaker**
4. Select **Local API** as the connection method
5. Enter the IP address of your Ultimaker printer
6. Click **Submit**

## Cloud API Setup (OAuth2 Authentication)

### Step 1: Request Client Credentials from Ultimaker

Before setting up the cloud API connection, you need to obtain client credentials from Ultimaker:

1. Contact Ultimaker support or visit [Ultimaker Developer Portal](https://developer.ultimaker.com/) to request client credentials
2. You will receive a **Client ID** and **Client Secret**
3. Make sure the redirect URI is set to: `https://my-home-assistant-url/auth/external/callback` (replace with your actual Home Assistant URL)

### Step 2: Configure Home Assistant

1. In Home Assistant, go to **Settings** > **Devices & Services**
2. Click the **+ ADD INTEGRATION** button
3. Search for and select **Ultimaker**
4. Select **Cloud API** as the connection method
5. You will be prompted to enter your client credentials:
   - Enter the **Client ID** and **Client Secret** you received from Ultimaker
   - Click **Submit**
6. You will be redirected to the Ultimaker login page
7. Log in with your Ultimaker account credentials
8. Authorize the application to access your Ultimaker account
9. You will be redirected back to Home Assistant
10. If you have multiple workspaces (organizations), you will be prompted to select which one to use
11. After selecting a workspace, if you have multiple clusters, you can select which one to use

### OAuth2 Flow and Workspace Switching

The integration uses OAuth2 for authentication with the Ultimaker Connect API. The flow works as follows:

1. You provide your client credentials (Client ID and Client Secret)
2. The integration redirects you to the Ultimaker login page
3. After logging in, you authorize the application to access your account
4. Ultimaker redirects back to Home Assistant with an authorization code
5. The integration exchanges the authorization code for an access token
6. The access token is used to make API requests
7. When the token expires, it is automatically refreshed

If you have multiple workspaces (organizations) in your Ultimaker account, you will be prompted to select which one to use during setup. The integration will remember your selection and use it for all future API requests.

To switch to a different workspace:
1. Remove the integration from Home Assistant
2. Add it again and select a different workspace during setup

## Configuration Options

After setting up the integration, you can configure the following options:

### Local API Options

- **Scan Interval** - How often to update data from the printer (in seconds)
- **Decimal Precision** - Number of decimal places for temperature values

### Cloud API Options

- **Scan Interval** - How often to update data from the cloud API (in seconds)
- **Decimal Precision** - Number of decimal places for temperature values
- **Cluster ID** - The ID of the cluster to use (if you have multiple clusters)

## Available Sensors

### Local API Sensors

- Printer status
- Print job state
- Print job progress
- Bed temperature
- Bed temperature target
- Bed type
- Hotend 1 temperature
- Hotend 1 temperature target
- Hotend 1 ID
- Hotend 2 temperature
- Hotend 2 temperature target
- Hotend 2 ID

### Cloud API Sensors

All Local API sensors plus:

- Cluster status
- Printer count
- Maintenance required
- Material remaining

## Troubleshooting

### Local API Issues

- Ensure your printer is powered on and connected to your network
- Verify the IP address is correct
- Check that your Home Assistant instance can reach the printer

### Cloud API Issues

- Verify your client credentials are correct
- Ensure your Ultimaker account has access to the printers
- Check your internet connection
- If you get authentication errors, try removing and re-adding the integration

## Support

If you encounter any issues, please report them on the [GitHub issue tracker](https://github.com/jellespijker/home-assistant-ultimaker/issues).
