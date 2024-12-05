import os
import json
from pathlib import Path
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
        store_tokens(tokens)
        typer.echo("Successfully logged in! 🎉")

    except requests.exceptions.RequestException as e:
        typer.echo(f"Login failed: {str(e)}", err=True)
        raise typer.Exit(1)


def logout():
    """
    Log out of your TaskNode account.
    """
    clear_tokens()
    typer.echo("Successfully logged out!")


def resend_verification(email: str = typer.Option(..., prompt=True)):
    """
    Resend the email verification code to your email address.
    """
    try:
        response = requests.post(f"{API_URL}/api/v1/users/resend-verification", json={"email": email})
        response.raise_for_status()
        typer.echo("\n✉️  A new verification code has been sent to your email.")

        # Prompt for verification code
        verification_code = typer.prompt("\nEnter the verification code from your email")

        # Submit the verification code - Changed endpoint from verify-email to verify
        verify_response = requests.post(
            f"{API_URL}/api/v1/users/verify",
            json={"email": email, "verification_code": verification_code},
        )
        verify_response.raise_for_status()
        typer.echo("\n✅ Email verified successfully! You can now login with command 'tasknode login'")

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
        response = requests.post(f"{API_URL}/api/v1/users/forgot-password", json={"email": email})
        response.raise_for_status()
        typer.echo("\n✉️  A password reset code has been sent to your email.")

        # Prompt for verification code and new password
        confirmation_code = typer.prompt("\nEnter the verification code from your email")
        new_password = typer.prompt("Enter your new password", hide_input=True, confirmation_prompt=True)

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
        typer.echo("\n✅ Password reset successfully! You can now login with your new password.")

    except requests.exceptions.RequestException as e:
        typer.echo(f"\n❌ Password reset failed: {str(e)}", err=True)
        raise typer.Exit(1)


def whoami():
    """
    Show information about the currently logged in user.
    """
    try:
        id_token = get_tokens().get("id_token")
        if not id_token:
            typer.echo(
                "Not logged in. Please login using 'tasknode login' or sign up using 'tasknode signup'.",
                err=True,
            )
            raise typer.Exit(1)

        try:
            decoded = jwt.decode(id_token, options={"verify_signature": False})
            typer.echo(f"\n👤 Logged in as: {decoded['email']}\n")
        except jwt.InvalidTokenError as e:
            typer.echo(f"Error decoding token: {str(e)}", err=True)
            raise typer.Exit(1)

    except Exception as e:
        typer.echo(
            "Not logged in. Please login using 'tasknode login' or sign up using 'tasknode signup'.",
            err=True,
        )
        raise typer.Exit(1)


# Helper functions
def refresh_tokens() -> Optional[str]:
    """
    Attempt to refresh the access token using the refresh token.
    Returns the new access token if successful, None otherwise.
    """
    try:
        tokens = get_tokens()
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            return None

        response = requests.post(
            f"{API_URL}/api/v1/users/refresh-token",
            params={"refresh_token": refresh_token},
        )
        response.raise_for_status()
        new_tokens = response.json()

        # Update stored tokens
        tokens.update(new_tokens)
        store_tokens(tokens)

        return new_tokens["access_token"]
    except requests.exceptions.RequestException as e:
        typer.echo(f"Token refresh failed: {str(e)}", err=True)
        return None


def get_valid_token() -> str:
    """
    Get a valid access token or raise an error if not possible.
    """
    tokens = get_tokens()
    access_token = tokens.get("access_token")

    if not access_token:
        print("You are not logged in.")
        action = typer.prompt(
            "\nWould you like to:\n1. Login\n2. Sign up\n3. Exit\nPlease choose (1-3)",
            type=int,
            default=3
        )
        
        if action == 1:
            # Prompt for credentials manually instead of relying on typer.Option
            email = typer.prompt("Email")
            password = typer.prompt("Password", hide_input=True)
            login(email=email, password=password)
            # After login, get the new tokens
            tokens = get_tokens()
            return tokens.get("access_token", "")
        elif action == 2:
            signup()
            # After signup, get the new tokens
            tokens = get_tokens()
            return tokens.get("access_token", "")
        else:
            exit(0)
    
    print("🔑 Successfully authenticated.")

    # Try to use the token
    response = requests.get(
        f"{API_URL}/api/v1/users/verify-token",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    if response.status_code == 401:  # Unauthorized - token might be expired
        refresh_token = tokens.get("refresh_token")
        if refresh_token:
            new_token = refresh_tokens()
            if new_token:
                return new_token
        typer.echo("Session expired. Please login again using 'tasknode login'.", err=True)
        raise typer.Exit(1)

    return access_token


def signup(
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True, confirmation_prompt=True),
):
    """
    Sign up for a TaskNode account.
    """
    try:
        # Submit signup request
        response = requests.post(
            f"{API_URL}/api/v1/users/signup",
            json={"email": email, "password": password},
        )
        response.raise_for_status()

        typer.echo("\n✅ Account created successfully!")
        typer.echo("\n✉️  A verification code has been sent to your email.")

        # Prompt for verification code
        verification_code = typer.prompt("\nEnter the verification code from your email")

        # Submit the verification code
        verify_response = requests.post(
            f"{API_URL}/api/v1/users/verify",
            json={"email": email, "verification_code": verification_code},
        )
        verify_response.raise_for_status()

        typer.echo("\n✅ Email verified successfully!\n")

        # Automatically log in the user
        login_response = requests.post(
            f"{API_URL}/api/v1/users/login",
            json={"email": email, "password": password},
        )
        login_response.raise_for_status()

        tokens = login_response.json()
        store_tokens(tokens)
        typer.echo("Successfully logged in! 🎉")

    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        if hasattr(e, "response") and e.response is not None:
            try:
                error_data = e.response.json()
                if "detail" in error_data:
                    error_msg = error_data["detail"]
            except:
                pass
        typer.echo(f"\n❌ Signup failed: {error_msg}", err=True)
        raise typer.Exit(1)


def get_config_dir() -> Path:
    """Get the TaskNode config directory."""
    config_dir = Path.home() / ".tasknode"
    config_dir.mkdir(exist_ok=True)
    return config_dir


def store_tokens(tokens: dict):
    """Store tokens in config file."""
    config_file = get_config_dir() / "credentials.json"
    with open(config_file, "w") as f:
        json.dump(tokens, f)
    # Windows doesn't support os.chmod(file, 0o600)
    if os.name != "nt":  # If not Windows
        os.chmod(config_file, 0o600)  # Set permissions to 600 (readable only by user)


def get_tokens() -> dict:
    """Get stored tokens."""
    config_file = get_config_dir() / "credentials.json"
    try:
        with open(config_file) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def clear_tokens():
    """Remove stored tokens."""
    config_file = get_config_dir() / "credentials.json"
    try:
        os.remove(config_file)
    except FileNotFoundError:
        pass
