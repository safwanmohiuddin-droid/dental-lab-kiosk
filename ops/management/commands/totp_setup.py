from base64 import b32encode

import qrcode
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django_otp.plugins.otp_totp.models import TOTPDevice


class Command(BaseCommand):
    help = "Give an admin user an authenticator-app code (TOTP). Prints a QR code to scan."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--replace", action="store_true", help="Remove existing devices first.")

    def handle(self, username, replace, **options):
        try:
            user = get_user_model().objects.get(username=username)
        except get_user_model().DoesNotExist as exc:
            raise CommandError(f"No user called {username}.") from exc
        devices = TOTPDevice.objects.filter(user=user)
        if devices.exists() and not replace:
            raise CommandError(f"{username} already has an authenticator. Use --replace.")
        devices.delete()
        device = TOTPDevice.objects.create(user=user, name="authenticator", confirmed=True)

        qr = qrcode.QRCode(border=1)
        qr.add_data(device.config_url)
        qr.print_ascii(out=self.stdout, invert=True)
        self.stdout.write(f"Or add this key by hand: {b32encode(device.bin_key).decode()}")
        self.stdout.write(f"Scan it with an authenticator app, then sign in to /admin/ as {user}.")
