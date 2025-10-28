"""
JupyterHub OAuth Service for Zenodo

This service runs as a JupyterHub managed service and handles OAuth authentication
at the Hub level (accessible at /hub/zenodo/*).

To enable in JupyterHub config (jupyterhub_config.py):

    import sys

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
        }
    ]

    # Add service routes to the Hub
    c.JupyterHub.services[0]['oauth_redirect_uri'] = 'https://your-hub.com/hub/zenodo/callback'

Required environment variables:
    - ZENODO_CLIENT_ID
    - ZENODO_CLIENT_SECRET
    - ZENODO_REDIRECT_URI (e.g., https://your-hub.com/hub/zenodo/callback)
    - ZENODO_AUTHORIZE_URL (default: https://zenodo.org/oauth/authorize)
    - ZENODO_TOKEN_URL (default: https://zenodo.org/oauth/token)
    - ZENODO_SCOPES (default: "deposit:write deposit:actions")
"""

import os
import sys
import json
import secrets
import urllib.parse
from tornado import web, ioloop
from tornado.httpclient import AsyncHTTPClient, HTTPRequest, HTTPClientError
from tornado.log import app_log


class ZenodoOAuthLoginHandler(web.RequestHandler):
    """Initiate Zenodo OAuth by redirecting to authorization page"""

    async def get(self):
        client_id = os.getenv('ZENODO_CLIENT_ID')
        redirect_uri = os.getenv('ZENODO_REDIRECT_URI')
        authorize_url = os.getenv('ZENODO_AUTHORIZE_URL', 'https://zenodo.org/oauth/authorize')
        scopes = os.getenv('ZENODO_SCOPES', 'deposit:write deposit:actions')

        if not client_id or not redirect_uri:
            self.set_status(500)
            self.write({
                'error': 'Missing configuration',
                'details': 'ZENODO_CLIENT_ID and ZENODO_REDIRECT_URI must be set'
            })
            return

        # CSRF protection via state parameter
        state = secrets.token_urlsafe(32)
        self.set_secure_cookie('zenodo_oauth_state', state, httponly=True, samesite='lax')

        params = {
            'client_id': client_id,
            'response_type': 'code',
            'redirect_uri': redirect_uri,
            'scope': scopes,
            'state': state,
        }

        # Infer sandbox flag from authorize_url
        if os.getenv('ZENODO_SANDBOX') is None:
            os.environ['ZENODO_SANDBOX'] = 'true' if 'sandbox.zenodo.org' in authorize_url else 'false'

        url = authorize_url + '?' + urllib.parse.urlencode(params)
        app_log.info(f"Zenodo OAuth: Redirecting to {authorize_url}")
        self.redirect(url)


class ZenodoOAuthCallbackHandler(web.RequestHandler):
    """Handle OAuth callback and exchange code for token"""

    async def get(self):
        error = self.get_argument('error', None)
        if error:
            self.set_status(400)
            self.write({'error': error})
            return

        code = self.get_argument('code', None)
        state = self.get_argument('state', None)

        expected_state = self.get_secure_cookie('zenodo_oauth_state')
        if expected_state:
            expected_state = expected_state.decode('utf-8') if isinstance(expected_state, bytes) else expected_state

        if not code or not state or not expected_state or state != expected_state:
            self.set_status(400)
            self.write({'error': 'Invalid OAuth state or missing code'})
            return

        client_id = os.getenv('ZENODO_CLIENT_ID')
        client_secret = os.getenv('ZENODO_CLIENT_SECRET')
        redirect_uri = os.getenv('ZENODO_REDIRECT_URI')
        token_url = os.getenv('ZENODO_TOKEN_URL', 'https://zenodo.org/oauth/token')

        if not client_id or not client_secret or not redirect_uri:
            self.set_status(500)
            self.write({
                'error': 'Missing configuration',
                'details': 'ZENODO_CLIENT_ID, ZENODO_CLIENT_SECRET and ZENODO_REDIRECT_URI must be set'
            })
            return

        body = urllib.parse.urlencode({
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri,
            'client_id': client_id,
            'client_secret': client_secret,
        })
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        app_log.info(f"Zenodo OAuth: Exchanging code for token at {token_url}")

        http = AsyncHTTPClient()
        try:
            response = await http.fetch(HTTPRequest(url=token_url, method='POST', headers=headers, body=body))
            data = json.loads(response.body.decode('utf-8'))
            app_log.info("Zenodo OAuth: Token exchange successful")
        except HTTPClientError as e:
            error_body = e.response.body.decode('utf-8') if e.response else 'no response'
            app_log.error(f"Zenodo OAuth: Token exchange failed - {e}, response: {error_body}")
            self.set_status(502)
            self.write({'error': 'Token exchange failed', 'details': str(e)})
            return
        except Exception as e:
            app_log.error(f"Zenodo OAuth: Unexpected error - {e}")
            self.set_status(500)
            self.write({'error': 'Unexpected error during token exchange', 'details': str(e)})
            return

        access_token = data.get('access_token')
        if not access_token:
            self.set_status(502)
            self.write({'error': 'No access_token in response'})
            return

        # Store token in environment (shared across Hub)
        # TODO: For multi-user scenarios, store in a database with user mapping
        os.environ['ZENODO_API_KEY'] = access_token
        app_log.info("Zenodo OAuth: Token stored successfully")

        # Redirect back to Hub home
        self.redirect('/hub/home')


class ZenodoOAuthLogoutHandler(web.RequestHandler):
    """Clear OAuth token"""

    async def post(self):
        os.environ.pop('ZENODO_API_KEY', None)
        self.clear_cookie('zenodo_oauth_state')
        self.write({'status': 'unlinked'})


def make_app():
    """Create the Tornado application"""
    cookie_secret = os.getenv('JUPYTERHUB_COOKIE_SECRET', os.getenv('COOKIE_SECRET', secrets.token_urlsafe(32)))

    return web.Application([
        (r'/hub/zenodo/login', ZenodoOAuthLoginHandler),
        (r'/hub/zenodo/callback', ZenodoOAuthCallbackHandler),
        (r'/hub/zenodo/logout', ZenodoOAuthLogoutHandler),
    ],
    cookie_secret=cookie_secret
    )


def main():
    """Main entry point for the Hub service"""
    import argparse

    parser = argparse.ArgumentParser(description='Zenodo OAuth Hub Service')
    parser.add_argument('--port', type=int, default=10101, help='Port to listen on')
    args = parser.parse_args()

    app = make_app()
    app.listen(args.port)

    app_log.info(f"Zenodo OAuth Hub Service starting on port {args.port}")
    app_log.info(f"Handlers available at:")
    app_log.info(f"  - /hub/zenodo/login")
    app_log.info(f"  - /hub/zenodo/callback")
    app_log.info(f"  - /hub/zenodo/logout")
    app_log.info(f"Environment check:")
    app_log.info(f"  - ZENODO_CLIENT_ID: {'✓ set' if os.getenv('ZENODO_CLIENT_ID') else '✗ missing'}")
    app_log.info(f"  - ZENODO_CLIENT_SECRET: {'✓ set' if os.getenv('ZENODO_CLIENT_SECRET') else '✗ missing'}")
    app_log.info(f"  - ZENODO_REDIRECT_URI: {os.getenv('ZENODO_REDIRECT_URI', '✗ missing')}")

    ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
