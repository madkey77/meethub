"""Google API authentication utilities supporting both service account and OAuth modes."""

import os
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from src.config import settings
from src.utils.exceptions import AuthenticationError
from src.utils.logging import get_logger

logger = get_logger(__name__)

# OAuth scopes required for personal mode
OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/meetings.space.readonly",
    "https://www.googleapis.com/auth/drive",  # Full Drive access to read recordings and upload transcripts
]

# Service account scopes for organization mode
SERVICE_ACCOUNT_SCOPES = OAUTH_SCOPES


def get_google_credentials() -> Any:
    """Get Google API credentials based on configured authentication mode.

    Returns:
        Credentials object (either service account or OAuth)

    Raises:
        AuthenticationError: If authentication fails
    """
    if settings.is_personal_mode:
        return _get_oauth_credentials()
    else:
        return _get_service_account_credentials()


def _get_service_account_credentials() -> service_account.Credentials:
    """Get service account credentials for organization-wide access.

    Returns:
        Service account credentials with domain-wide delegation

    Raises:
        AuthenticationError: If service account authentication fails
    """
    try:
        if not settings.google_service_account_path.exists():
            raise AuthenticationError(
                f"Service account file not found: {settings.google_service_account_path}",
                details={"path": str(settings.google_service_account_path)},
            )

        credentials = service_account.Credentials.from_service_account_file(
            str(settings.google_service_account_path),
            scopes=SERVICE_ACCOUNT_SCOPES,
        )

        # Delegate to admin email for domain-wide access
        if settings.google_workspace_admin_email:
            credentials = credentials.with_subject(settings.google_workspace_admin_email)
            logger.info(
                "Service account credentials loaded with domain-wide delegation",
                admin_email=settings.google_workspace_admin_email,
            )
        else:
            logger.warning(
                "No admin email configured - service account may have limited access"
            )

        return credentials

    except Exception as e:
        raise AuthenticationError(
            f"Failed to load service account credentials: {e}",
            details={"path": str(settings.google_service_account_path)},
        ) from e


def _get_oauth_credentials() -> Credentials:
    """Get OAuth credentials for personal account access.

    Uses stored token if available, otherwise initiates OAuth flow.

    Returns:
        OAuth credentials

    Raises:
        AuthenticationError: If OAuth authentication fails
    """
    try:
        creds = None

        # Check if we have a stored token
        if settings.google_oauth_token_path.exists():
            try:
                logger.debug(
                    "Attempting to load token",
                    token_path=str(settings.google_oauth_token_path),
                    requested_scopes=OAUTH_SCOPES,
                )
                creds = Credentials.from_authorized_user_file(
                    str(settings.google_oauth_token_path),
                    OAUTH_SCOPES,
                )

                # Check if scopes have changed
                if creds.scopes and set(creds.scopes) != set(OAUTH_SCOPES):
                    logger.warning(
                        "OAuth scopes have changed, forcing re-authentication",
                        old_scopes=creds.scopes,
                        new_scopes=OAUTH_SCOPES,
                    )
                    # Delete old token file to force fresh auth
                    settings.google_oauth_token_path.unlink()
                    creds = None
                else:
                    logger.info("Loaded OAuth credentials from token file")
            except Exception as e:
                logger.warning(
                    "Failed to load stored token, will re-authenticate",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                # If there's an error, delete the token file and start fresh
                if settings.google_oauth_token_path.exists():
                    settings.google_oauth_token_path.unlink()
                    logger.info("Deleted corrupted token file")
                creds = None

        # If no valid credentials, authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                # Refresh expired token
                logger.info("Refreshing expired OAuth token")
                creds.refresh(Request())
                logger.info("OAuth token refreshed successfully")
            else:
                # Run OAuth flow
                if not settings.google_oauth_credentials_path.exists():
                    raise AuthenticationError(
                        f"OAuth credentials file not found: {settings.google_oauth_credentials_path}",
                        details={"path": str(settings.google_oauth_credentials_path)},
                    )

                logger.info("Starting OAuth authentication flow")
                # Force fresh authentication by not loading cached credentials
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(settings.google_oauth_credentials_path),
                    scopes=OAUTH_SCOPES,
                )

                # Check if we're in WSL or headless environment
                import os
                is_wsl = "WSL" in os.uname().release or "microsoft" in os.uname().release.lower()

                if is_wsl or not os.environ.get("DISPLAY"):
                    # Manual authentication for WSL/headless
                    logger.info("=" * 80)
                    logger.info("WSL/Headless environment detected - Using manual authentication")
                    logger.info("=" * 80)

                    # For Desktop app, we need to start a local server but get the URL manually
                    # Generate authorization URL with localhost redirect
                    flow.redirect_uri = "http://localhost:8080/"
                    auth_url, _ = flow.authorization_url(
                        prompt='consent',
                        access_type='offline',
                        include_granted_scopes='true'
                    )

                    print("\n" + "=" * 80)
                    print("MANUAL AUTHENTICATION REQUIRED (WSL)")
                    print("=" * 80)
                    print("\n1. Copy this URL and open it in your Windows browser:")
                    print(f"\n{auth_url}\n")
                    print("2. Sign in and authorize the application")
                    print("3. After authorization, you'll see an error page (can't reach localhost)")
                    print("4. Copy the ENTIRE URL from your browser address bar")
                    print("   (It will look like: http://localhost:8080/?code=...&scope=...)")
                    print("5. Paste the complete URL below\n")
                    print("=" * 80)

                    # Get redirect URL from user
                    redirect_response = input("\nPaste the complete redirect URL here: ").strip()

                    # Extract code from URL
                    from urllib.parse import urlparse, parse_qs
                    parsed = urlparse(redirect_response)

                    # Handle both http://localhost and https://localhost
                    if parsed.hostname != 'localhost' and 'code=' not in redirect_response:
                        raise AuthenticationError(
                            "Invalid redirect URL. Please copy the entire URL from your browser address bar.",
                            details={"provided_url": redirect_response}
                        )

                    # Extract code from query parameters
                    params = parse_qs(parsed.query)
                    if 'code' not in params:
                        raise AuthenticationError(
                            "No authorization code found in URL. Please make sure you copied the complete URL.",
                            details={"provided_url": redirect_response}
                        )

                    code = params['code'][0]

                    # Exchange code for credentials
                    flow.fetch_token(code=code)
                    creds = flow.credentials
                    logger.info("OAuth authentication successful via manual flow")
                else:
                    # Try local server flow for normal environments
                    try:
                        logger.info("Attempting to open browser for authentication...")
                        creds = flow.run_local_server(port=0, open_browser=True)
                        logger.info("OAuth authentication successful")
                    except Exception as e:
                        logger.error(f"Local server flow failed: {e}")
                        raise AuthenticationError(
                            "Failed to authenticate. If running in WSL, the browser redirect may not work. "
                            "Try setting DISPLAY environment variable or use manual flow.",
                            details={"error": str(e)},
                        )

            # Save token for future use
            settings.google_oauth_token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(settings.google_oauth_token_path, "w") as token_file:
                token_file.write(creds.to_json())
            logger.info(
                "OAuth token saved",
                token_path=str(settings.google_oauth_token_path),
            )

        return creds

    except Exception as e:
        raise AuthenticationError(
            f"Failed to authenticate with OAuth: {e}",
            details={"credentials_path": str(settings.google_oauth_credentials_path)},
        ) from e


def revoke_oauth_token() -> None:
    """Revoke and delete stored OAuth token.

    Useful for logging out or switching accounts.
    """
    try:
        if settings.google_oauth_token_path.exists():
            # Load and revoke token
            creds = Credentials.from_authorized_user_file(
                str(settings.google_oauth_token_path),
                OAUTH_SCOPES,
            )

            if creds and creds.valid:
                # Revoke token
                import requests

                requests.post(
                    "https://oauth2.googleapis.com/revoke",
                    params={"token": creds.token},
                    headers={"content-type": "application/x-www-form-urlencoded"},
                )
                logger.info("OAuth token revoked")

            # Delete token file
            settings.google_oauth_token_path.unlink()
            logger.info("OAuth token file deleted")

    except Exception as e:
        logger.error(
            "Failed to revoke OAuth token",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


def get_authenticated_user_email() -> str | None:
    """Get email of authenticated user (OAuth mode only).

    Returns:
        User email if in OAuth mode and available, None otherwise
    """
    if not settings.is_personal_mode:
        return None

    try:
        if settings.google_oauth_token_path.exists():
            creds = Credentials.from_authorized_user_file(
                str(settings.google_oauth_token_path),
                OAUTH_SCOPES,
            )

            # Email is in the token info
            import json

            with open(settings.google_oauth_token_path) as f:
                token_data = json.load(f)
                # Note: email might not be in token, would need to call userinfo API
                return token_data.get("client_id")  # This is not email, just client ID

    except Exception as e:
        logger.warning("Failed to get user email from token", error=str(e))

    return None
