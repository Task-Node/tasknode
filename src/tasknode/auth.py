import keyring
import jwt
import requests
import typer
from typing import Optional

from tasknode.constants import API_URL, SERVICE_NAME

# Commands


def login(
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True),
):
    """
    Log in to your TaskNode account.
    """
    try:
        response = requests.post(
            f"{API_URL}/api/v1/users/login",
            json={"email": email, "password": password},
        )

        # Check if response contains an error message
        if response.status_code == 401:
            typer.echo(
                f"Login failed: Invalid credentials. If you forgot your password, you can reset it using 'tasknode reset-password'. To sign up, use 'tasknode signup'.",
                err=True,
            )
            raise typer.Exit(1)
        if response.status_code != 200:
            error_data = response.json()
            if "detail" in error_data:
                typer.echo(f"Login failed: {error_data['detail']}", err=True)
                raise typer.Exit(1)

        tokens = response.json()

        # Store tokens securely
        keyring.set_password(SERVICE_NAME, "access_token", tokens["access_token"])
        keyring.set_password(SERVICE_NAME, "id_token", tokens["id_token"])
        keyring.set_password(SERVICE_NAME, "refresh_token", tokens["refresh_token"])

        typer.echo("Successfully logged in! 🎉")

    except requests.exceptions.RequestException as e:
        typer.echo(f"Login failed: {str(e)}", err=True)
        raise typer.Exit(1)


def logout():
    """
    Log out of your TaskNode account.
    """
    try:
        keyring.delete_password(SERVICE_NAME, "access_token")
        keyring.delete_password(SERVICE_NAME, "id_token")
        keyring.delete_password(SERVICE_NAME, "refresh_token")
        typer.echo("Successfully logged out!")
    except keyring.errors.PasswordDeleteError:
        typer.echo("Already logged out!")


def resend_verification(email: str = typer.Option(..., prompt=True)):
    """
    Resend the email verification code to your email address.
    """
    try:
        response = requests.post(
            f"{API_URL}/api/v1/users/resend-verification", json={"email": email}
        )
        response.raise_for_status()
        typer.echo("\n✉️  A new verification code has been sent to your email.")

        # Prompt for verification code
        verification_code = typer.prompt(
            "\nEnter the verification code from your email"
        )

        # Submit the verification code - Changed endpoint from verify-email to verify
        verify_response = requests.post(
            f"{API_URL}/api/v1/users/verify",
            json={"email": email, "verification_code": verification_code},
        )
        verify_response.raise_for_status()
        typer.echo(
            "\n✅ Email verified successfully! You can now login with command 'tasknode login'"
        )

    except requests.exceptions.RequestException as e:
        typer.echo(f"\n❌ Verification failed: {str(e)}", err=True)
        raise typer.Exit(1)


def reset_password(
    email: str = typer.Option(..., prompt=True),
):
    """
    Reset your TaskNode account password.
    """
    try:
        # Request password reset code
        response = requests.post(
            f"{API_URL}/api/v1/users/forgot-password", json={"email": email}
        )
        response.raise_for_status()
        typer.echo("\n✉️  A password reset code has been sent to your email.")

        # Prompt for verification code and new password
        confirmation_code = typer.prompt(
            "\nEnter the verification code from your email"
        )
        new_password = typer.prompt(
            "Enter your new password", hide_input=True, confirmation_prompt=True
        )

        # Confirm password reset
        response = requests.post(
            f"{API_URL}/api/v1/users/confirm-forgot-password",
            json={
                "email": email,
                "confirmation_code": confirmation_code,
                "new_password": new_password,
            },
        )
        response.raise_for_status()
        typer.echo(
            "\n✅ Password reset successfully! You can now login with your new password."
        )

    except requests.exceptions.RequestException as e:
        typer.echo(f"\n❌ Password reset failed: {str(e)}", err=True)
        raise typer.Exit(1)


def whoami():
    """
    Show information about the currently logged in user.
    """
    try:
        id_token = keyring.get_password(SERVICE_NAME, "id_token")
        if not id_token:
            typer.echo("Not logged in. Please login using 'tasknode login'", err=True)
            raise typer.Exit(1)

        try:
            decoded = jwt.decode(id_token, options={"verify_signature": False})
            typer.echo(f"\n👤 Logged in as: {decoded['email']}\n")
        except jwt.InvalidTokenError as e:
            typer.echo(f"Error decoding token: {str(e)}", err=True)
            raise typer.Exit(1)

    except keyring.errors.KeyringError as e:
        typer.echo(f"Error accessing keyring: {str(e)}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo("Not logged in. Please login using 'tasknode login'", err=True)
        raise typer.Exit(1)


# Helper functions
def refresh_tokens() -> Optional[str]:
    """
    Attempt to refresh the access token using the refresh token.
    Returns the new access token if successful, None otherwise.
    """
    try:
        refresh_token = keyring.get_password(SERVICE_NAME, "refresh_token")
        if not refresh_token:
            return None

        response = requests.post(
            f"{API_URL}/api/v1/users/refresh-token",
            params={"refresh_token": refresh_token},
        )
        response.raise_for_status()
        tokens = response.json()

        # Store new tokens
        keyring.set_password(SERVICE_NAME, "access_token", tokens["access_token"])
        keyring.set_password(SERVICE_NAME, "id_token", tokens["id_token"])

        return tokens["access_token"]
    except requests.exceptions.RequestException as e:
        typer.echo(f"Token refresh failed: {str(e)}", err=True)
        return None
    except keyring.errors.KeyringError as e:
        typer.echo(f"Keyring error: {str(e)}", err=True)
        return None


def get_valid_token() -> str:
    """
    Get a valid access token or raise an error if not possible.
    """
    access_token = keyring.get_password(SERVICE_NAME, "access_token")
    if not access_token:
        typer.echo("Please login first using 'tasknode login'", err=True)
        raise typer.Exit(1)

    # Try to use the token
    response = requests.get(
        f"{API_URL}/api/v1/users/verify-token",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    if response.status_code == 401:  # Unauthorized - token might be expired
        new_token = refresh_tokens()
        if new_token:
            return new_token
        typer.echo(
            "Session expired. Please login again using 'tasknode login'", err=True
        )
        raise typer.Exit(1)

    return access_token
