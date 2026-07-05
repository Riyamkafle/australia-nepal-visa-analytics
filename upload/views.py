"""
Upload views for the Nepal Student Visa Analytics Dashboard.
Handles CSV and Excel file uploads via HTML form and REST API.
"""

import os
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status

from .models import UploadLog
from .utils import process_upload


def _get_file_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext == '.csv':
        return 'csv'
    elif ext in ('.xlsx', '.xls'):
        return 'excel'
    return 'unknown'


# ─── HTML Upload Page ─────────────────────────────────────────────────────────

def upload_page(request):
    """Upload page with file upload forms and history."""
    if request.method == 'POST':
        uploaded_file  = request.FILES.get('file')
        target_table   = request.POST.get('target_table', '').strip() or None

        if not uploaded_file:
            messages.error(request, 'No file selected.')
            return redirect('upload')

        file_type = _get_file_type(uploaded_file.name)
        if file_type == 'unknown':
            messages.error(request, 'Unsupported file type. Please upload CSV or Excel files only.')
            return redirect('upload')

        result = process_upload(uploaded_file, file_type, target_table)

        log = UploadLog.objects.create(
            filename    = uploaded_file.name,
            file_type   = file_type,
            rows_loaded = result['rows_loaded'],
            status      = result['status'],
            notes       = result.get('error') or f"Loaded into table: {result['table']}",
        )

        if result['status'] == 'success':
            messages.success(
                request,
                f"✓ Successfully loaded {result['rows_loaded']:,} rows into '{result['table']}'."
            )
        else:
            messages.error(request, f"✗ Upload failed: {result['error']}")

        return redirect('upload')

    # GET: render page with upload history
    history = UploadLog.objects.all()[:50]
    return render(request, 'dashboard/upload.html', {'history': history})


# ─── REST API Upload Endpoints ────────────────────────────────────────────────

@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def upload_csv_api(request):
    """
    POST /api/upload/csv/
    Upload a CSV file to reload a target table.
    Form fields: file (required), target_table (optional)
    """
    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        return Response({'error': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

    if not uploaded_file.name.endswith('.csv'):
        return Response({'error': 'File must be a .csv'}, status=status.HTTP_400_BAD_REQUEST)

    target_table = request.data.get('target_table', '').strip() or None
    result = process_upload(uploaded_file, 'csv', target_table)

    UploadLog.objects.create(
        filename    = uploaded_file.name,
        file_type   = 'csv',
        rows_loaded = result['rows_loaded'],
        status      = result['status'],
        notes       = result.get('error') or f"Loaded into: {result['table']}",
    )

    if result['status'] == 'success':
        return Response({
            'status':      'success',
            'filename':    uploaded_file.name,
            'table':       result['table'],
            'rows_loaded': result['rows_loaded'],
        }, status=status.HTTP_201_CREATED)
    else:
        return Response({
            'status': 'error',
            'error':  result['error'],
        }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def upload_excel_api(request):
    """
    POST /api/upload/excel/
    Upload an Excel (.xlsx/.xls) file to reload a target table.
    Form fields: file (required), target_table (optional)
    """
    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        return Response({'error': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

    name = uploaded_file.name.lower()
    if not (name.endswith('.xlsx') or name.endswith('.xls')):
        return Response({'error': 'File must be .xlsx or .xls'}, status=status.HTTP_400_BAD_REQUEST)

    target_table = request.data.get('target_table', '').strip() or None
    result = process_upload(uploaded_file, 'excel', target_table)

    UploadLog.objects.create(
        filename    = uploaded_file.name,
        file_type   = 'excel',
        rows_loaded = result['rows_loaded'],
        status      = result['status'],
        notes       = result.get('error') or f"Loaded into: {result['table']}",
    )

    if result['status'] == 'success':
        return Response({
            'status':      'success',
            'filename':    uploaded_file.name,
            'table':       result['table'],
            'rows_loaded': result['rows_loaded'],
        }, status=status.HTTP_201_CREATED)
    else:
        return Response({
            'status': 'error',
            'error':  result['error'],
        }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
