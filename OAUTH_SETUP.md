# Zenodo OAuth Setup Guide

This guide explains how to configure Zenodo OAuth for both **localhost testing** and **JupyterHub production** environments.

## Architecture Overview

The extension supports two deployment modes:

1. **Localhost/Standalone JupyterLab**: OAuth handlers run in the single-user server
2. **JupyterHub Production**: OAuth handlers run as a Hub-level service

The frontend automatically detects which environment it's running in and redirects accordingly.

---

## 1. Localhost Testing Setup

### Prerequisites
- Zenodo Sandbox account: https://sandbox.zenodo.org
- OAuth application created at: https://sandbox.zenodo.org/account/settings/applications/

### Step 1: Create OAuth Application in Zenodo Sandbox

1. Go to https://sandbox.zenodo.org/account/settings/applications/
2. Click "New application"
3. Fill in:
   - **Name**: Zenodo JupyterLab Extension (Localhost)
   - **Description**: OAuth for local testing
   - **Redirect URIs** (add this):
     ```
     http://localhost:8888/zenodo-jupyterlab/oauth/callback
     ```
   - **Scopes**: Select `deposit:write` and `deposit:actions`
4. Save and note the **Client ID** and **Client Secret**

### Step 2: Configure Environment Variables

Create a `.env` file in the project root:

```bash
ZENODO_CLIENT_ID=<your-client-id>
ZENODO_CLIENT_SECRET=<your-client-secret>
ZENODO_REDIRECT_URI=http://localhost:8888/zenodo-jupyterlab/oauth/callback
ZENODO_SANDBOX=true
ZENODO_AUTHORIZE_URL=https://sandbox.zenodo.org/oauth/authorize
ZENODO_TOKEN_URL=https://sandbox.zenodo.org/oauth/token
```

### Step 3: Start JupyterLab

```bash
# Activate virtual environment
source venv/bin/activate

# Load environment variables and start JupyterLab
set -a && source .env && set +a && jupyter-lab
```

### Step 4: Test OAuth Flow

1. Open JupyterLab in your browser
2. Navigate to the Zenodo tab in the sidebar
3. Click "Login with Zenodo"
4. Authorize the application on Zenodo Sandbox
5. You should be redirected back to JupyterLab with authentication complete

---

## 2. JupyterHub Production Setup

### Prerequisites
- JupyterHub deployed (e.g., https://your-hub.com)
- Zenodo account (production or sandbox)
- OAuth application created in Zenodo

### Step 1: Create OAuth Application in Zenodo

1. Go to https://zenodo.org/account/settings/applications/ (or sandbox)
2. Click "New application"
3. Fill in:
   - **Name**: Zenodo JupyterLab Extension (Production)
   - **Description**: OAuth for JupyterHub
   - **Redirect URIs** (add this):
     ```
     https://your-hub.com/hub/zenodo/callback
     ```
   - **Scopes**: Select `deposit:write` and `deposit:actions`
4. Save and note the **Client ID** and **Client Secret**

### Step 2: Configure JupyterHub Service

Edit your `jupyterhub_config.py`:

```python
import sys

# Add Zenodo OAuth service
c.JupyterHub.services = [
    {
        'name': 'zenodo-oauth',
        'url': 'http://127.0.0.1:10101',
        'command': [
            sys.executable,
            '-m', 'zenodo_jupyterlab.hub_service',
            '--port=10101',
        ],
        'oauth_no_confirm': True,
        'environment': {
            'ZENODO_CLIENT_ID': '<your-client-id>',
            'ZENODO_CLIENT_SECRET': '<your-client-secret>',
            'ZENODO_REDIRECT_URI': 'https://your-hub.com/hub/zenodo/callback',
            # For production Zenodo (default):
            # 'ZENODO_AUTHORIZE_URL': 'https://zenodo.org/oauth/authorize',
            # 'ZENODO_TOKEN_URL': 'https://zenodo.org/oauth/token',
            # For sandbox Zenodo:
            'ZENODO_AUTHORIZE_URL': 'https://sandbox.zenodo.org/oauth/authorize',
            'ZENODO_TOKEN_URL': 'https://sandbox.zenodo.org/oauth/token',
            'ZENODO_SANDBOX': 'true',
        },
    }
]

# Route /hub/zenodo/* to the service
c.JupyterHub.load_roles = [
    {
        'name': 'zenodo-oauth-service',
        'scopes': ['access:services', 'read:users'],
        'services': ['zenodo-oauth'],
    }
]
```

### Step 3: Install Extension in User Environments

The extension needs to be installed in the user's notebook environment:

```bash
pip install -e /path/to/zenodo-jupyterlab-extension
jupyter server extension enable zenodo_jupyterlab.server
```

Or add to your Docker image / conda environment.

### Step 4: Restart JupyterHub

```bash
sudo systemctl restart jupyterhub
# or
jupyterhub -f /path/to/jupyterhub_config.py
```

### Step 5: Test OAuth Flow

1. Log into JupyterHub and start a server
2. Navigate to the Zenodo tab in the sidebar
3. Click "Login with Zenodo"
4. You'll be redirected to `/hub/zenodo/login` (Hub service)
5. Authorize the application on Zenodo
6. You should be redirected back to JupyterHub

---

## Redirect URI Summary

| Environment | OAuth Handlers Location | Redirect URI |
|-------------|------------------------|--------------|
| **Localhost** | Single-user server | `http://localhost:8888/zenodo-jupyterlab/oauth/callback` |
| **JupyterHub** | Hub service | `https://your-hub.com/hub/zenodo/callback` |

**Important**: You need to register **both** redirect URIs in your Zenodo OAuth application if you want to support both localhost testing and production deployment.

---

## Troubleshooting

### Localhost Issues

**Problem**: 404 error on `/zenodo-jupyterlab/oauth/login`

**Solution**: Make sure the server extension is enabled:
```bash
jupyter server extension enable zenodo_jupyterlab.server
jupyter server extension list
```

**Problem**: "Invalid redirect URI" error from Zenodo

**Solution**: Check that your `.env` file has the correct redirect URI that matches what's registered in Zenodo:
```bash
ZENODO_REDIRECT_URI=http://localhost:8888/zenodo-jupyterlab/oauth/callback
```

### JupyterHub Issues

**Problem**: 404 error on `/hub/zenodo/login`

**Solution**: Check that the Hub service is running:
```bash
# Check JupyterHub logs
journalctl -u jupyterhub -f

# Look for:
# "Zenodo OAuth Hub Service starting on port 10101"
```

**Problem**: "Mismatching redirect URI" from Zenodo

**Solution**: Verify the redirect URI in `jupyterhub_config.py` matches what's registered in Zenodo:
- Config: `https://your-hub.com/hub/zenodo/callback`
- Zenodo app: Must include this exact URI

### Debug Logging

Enable debug logging to see OAuth flow details:

**Localhost**:
```bash
jupyter-lab --debug
```

**JupyterHub service**: Check the service logs in JupyterHub admin panel or system logs.

---

## Security Considerations

1. **Never commit** `.env` files with secrets to version control
2. **Use HTTPS** in production - OAuth over HTTP is insecure
3. **Rotate credentials** periodically
4. **Limit scopes** to only what's needed (e.g., `deposit:write deposit:actions`)
5. For multi-user JupyterHub, consider implementing **per-user token storage** (database or encrypted storage) instead of storing in environment variables

---

## Production Notes

### Token Storage

The current implementation stores the OAuth token in an environment variable (`ZENODO_API_KEY`). For production multi-user deployments, you should implement proper token storage:

- Store tokens in a database with user mapping
- Or use JupyterHub's OAuth token system
- Encrypt tokens at rest
- Implement token refresh logic

### Multi-User Considerations

In the current setup, the Hub service stores one token in memory. For multiple users:

1. Modify `hub_service.py` to store tokens per-user in a database
2. Pass the authenticated user's username from JupyterHub to the service
3. Retrieve the correct token when making API calls

This is beyond the scope of this basic setup but is essential for production multi-user environments.
