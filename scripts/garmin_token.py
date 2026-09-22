"""Create a Garmin token locally for the GARMIN_TOKEN GitHub Actions secret."""

import argparse
import configparser
import getpass
import os
from pathlib import Path

import garth
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--session-dir", help="Reuse existing Garth OAuth JSON files instead of logging in")
    source.add_argument("--credentials", type=Path, help="Read GARMIN_EMAIL, GARMIN_PASSWORD and GARMIN_AUTH_DOMAIN from an INI [sync] section")
    parser.add_argument("--check-only", action="store_true", help="Test login and profile access without exporting a token")
    args = parser.parse_args()
    domain = os.getenv("GARMIN_AUTH_DOMAIN", "COM").upper()
    if args.credentials:
        config = configparser.ConfigParser(interpolation=None)
        with args.credentials.open(encoding="utf-8-sig") as settings:
            config.read_file(settings)
        credentials = config["sync"]
        email = credentials.get("GARMIN_EMAIL", "").strip()
        password = credentials.get("GARMIN_PASSWORD", "")
        domain = credentials.get("GARMIN_AUTH_DOMAIN", "COM").strip().upper()
        if not email or not password or domain not in ("COM", "CN"):
            raise ValueError("Fill GARMIN_EMAIL, GARMIN_PASSWORD and GARMIN_AUTH_DOMAIN (COM/CN) in [sync].")
    client = garth.Client(
        domain="garmin.cn" if domain == "CN" else "garmin.com"
    )
    if args.session_dir:
        client.load(args.session_dir)
    else:
        if not args.credentials:
            email = os.getenv("GARMIN_EMAIL") or input("Garmin email: ").strip()
            password = os.getenv("GARMIN_PASSWORD") or getpass.getpass("Garmin password: ")
        client.login(email, password)  # Garth prompts for MFA here if required.
    # Validate API access and refresh OAuth2 before exporting. Never print tokens.
    client.sess.headers.pop("User-Agent", None)
    client.username
    if args.check_only:
        print("SUCCESS: Garmin login and profile request succeeded.")
        return
    destination = Path(__file__).resolve().parents[1] / ".garmin-token"
    with open(destination, "w", opener=lambda path, flags: os.open(path, flags, 0o600)) as output:
        output.write(client.dumps())
    print(f"Token saved to {destination}. Copy its contents into the GARMIN_TOKEN repository secret.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Login exceptions can contain a CAS ticket; keep it out of terminal logs.
        raise SystemExit(
            f"Garmin authentication/check failed ({type(error).__name__}). "
            "Check the credentials file, account region and MFA. If login is blocked, "
            "stop retrying and use --session-dir with an existing valid Garth session."
        ) from None
