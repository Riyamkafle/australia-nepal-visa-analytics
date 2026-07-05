from django.contrib import admin
from .models import UploadLog


@admin.register(UploadLog)
class UploadLogAdmin(admin.ModelAdmin):
    list_display  = ('filename', 'file_type', 'rows_loaded', 'status', 'uploaded_at')
    list_filter   = ('status', 'file_type')
    search_fields = ('filename', 'notes')
    readonly_fields = ('uploaded_at',)
    ordering      = ('-uploaded_at',)
