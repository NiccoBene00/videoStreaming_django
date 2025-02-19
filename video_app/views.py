from django.shortcuts import render, get_object_or_404
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import VideoSource
from .streaming import start_recording, stop_recording, add_watermark_and_save, send_recording
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
import json

def index(request):
    """Home Page - Mostra la lista degli stream"""
    sources = VideoSource.objects.all()
    return render(request, 'index.html', {'sources': sources})


def stream_view(request, source_id):
    """Pagina dello stream e dei controlli"""
    source = get_object_or_404(VideoSource, id=source_id)
    return render(request, 'stream_view.html', {'source': source})


def video_feed(request, source_id):
    """Flusso video MJPEG - Mostra il flusso live"""
    source = get_object_or_404(VideoSource, id=source_id)

    def generate():
        import cv2
        cap = cv2.VideoCapture(source.url)
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            _, buffer = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

        cap.release()

    return StreamingHttpResponse(generate(), content_type='multipart/x-mixed-replace; boundary=frame')


@csrf_exempt
def start_recording_view(request, source_id):
    """Avvia la registrazione"""
    if request.method == 'POST':
        start_recording(source_id)
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})


@csrf_exempt
def stop_recording_view(request, source_id):
    """Ferma la registrazione"""
    if request.method == 'POST':
        stop_recording(source_id)

        # Il nome del file è coerente con il pattern usato in streaming.py
        filename = f'source_{source_id}.mp4'

        return JsonResponse({'success': True, 'filename': filename})

    return JsonResponse({'success': False})




@csrf_exempt
def add_watermark_view(request, source_id):
    """Applica il watermark al video registrato"""
    if request.method == 'POST':
        text = request.POST.get('watermark_text')
        print(f"Applying watermark with text: '{text}'")
        color = request.POST.get('watermark_color', '#ffffff')
        font_size = float(request.POST.get('watermark_size', '1.5'))

        if not text:
            return JsonResponse({'success': False, 'error': 'Watermark text is empty'})

        add_watermark_and_save(source_id, text, color, font_size)
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})


@csrf_exempt
def send_recording_view(request, source_id):
    """
    Invia il video registrato a un URL esterno.
    """
    if request.method == 'POST':
        output_url = request.POST.get('output_url')

        if not output_url:
            return JsonResponse({'success': False, 'error': 'Output URL mancante'})

        success, error_message = send_recording(source_id, output_url)

        if success:
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': error_message})

    return JsonResponse({'success': False, 'error': 'Metodo non consentito'})


@csrf_exempt
def add_video_source(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            name = data.get('name')
            url = data.get('url')
            source_type = data.get('source_type')

            # Validazioni lato server
            if not name.strip():
                return JsonResponse({'success': False, 'error': 'Name cannot be empty.'})

            validate = URLValidator()
            try:
                validate(url)
            except ValidationError:
                return JsonResponse({'success': False, 'error': 'Invalid URL.'})

            if source_type not in ['rtsp', 'mjpg']:
                return JsonResponse({'success': False, 'error': 'Invalid source type.'})

            # Creazione della risorsa
            VideoSource.objects.create(name=name, url=url, source_type=source_type)

            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request'})