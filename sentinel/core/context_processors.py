from .models import MediaFile

def media_stats(request):
    """Context processor to provide media status counts to all templates"""
    stats = {
        'processed': MediaFile.objects.filter(status='processed').count(),
        'processing': MediaFile.objects.filter(status='processing').count(),
        'failed': MediaFile.objects.filter(status='failed').count(),
        'stopped': MediaFile.objects.filter(status='stopped').count(),
    }
    return {'media_stats': stats}
