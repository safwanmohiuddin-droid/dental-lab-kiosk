import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

LINK_LIFETIME = timedelta(hours=24)


def hash_token(token):
    # SHA-256 is enough: the token is 256 random bits, not a guessable password.
    return hashlib.sha256(token.encode()).hexdigest()


class Device(models.Model):
    """A shared tablet allowed to offer PIN sign-in (ADR 0009)."""

    name = models.CharField(max_length=100)
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    link_expires_at = models.DateTimeField(null=True, editable=False)
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, editable=False
    )
    registered_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_seen_at = models.DateTimeField(null=True, blank=True, editable=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def new_link_token(self, user):
        """Issue a fresh one-time link. Unregisters the device until the link is opened."""
        token = secrets.token_urlsafe(32)
        self.token_hash = hash_token(token)
        self.link_expires_at = timezone.now() + LINK_LIFETIME
        self.registered_at = None
        self.registered_by = user
        return token
