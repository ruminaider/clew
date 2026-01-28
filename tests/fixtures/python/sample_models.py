"""Sample Django models for testing chunker."""

from django.db import models


class Prescription(models.Model):
    """A prescription for medication."""

    user = models.ForeignKey("User", on_delete=models.CASCADE)
    medication = models.CharField(max_length=255)
    expires_at = models.DateTimeField()

    def is_expired(self) -> bool:
        """Check if prescription has passed expiration date."""
        from django.utils import timezone

        return timezone.now() > self.expires_at


def create_prescription(user, medication: str) -> "Prescription":
    """Factory function to create a prescription."""
    from datetime import timedelta

    from django.utils import timezone

    return Prescription.objects.create(
        user=user, medication=medication, expires_at=timezone.now() + timedelta(days=30)
    )
