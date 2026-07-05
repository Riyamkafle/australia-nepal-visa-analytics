from django.db import models


class UploadLog(models.Model):
    """Tracks every CSV/Excel upload and automated import."""

    STATUS_CHOICES = [
        ('success', 'Success'),
        ('error',   'Error'),
        ('partial', 'Partial'),
    ]

    FILE_TYPE_CHOICES = [
        ('csv',   'CSV'),
        ('excel', 'Excel'),
        ('auto',  'Automated Import'),
    ]

    filename    = models.CharField(max_length=255)
    file_type   = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES, default='csv')
    rows_loaded = models.IntegerField(default=0)
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default='success')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    notes       = models.TextField(blank=True, null=True)

    class Meta:
        managed  = True
        db_table = 'upload_logs'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"UploadLog({self.filename}, {self.status}, {self.uploaded_at:%Y-%m-%d %H:%M})"
