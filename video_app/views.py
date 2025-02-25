import traceback
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.shortcuts import render, get_object_or_404, redirect
from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from .models import VideoSource
from .streaming import start_recording, stop_recording, add_watermark_and_save, send_recording
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import json
import requests
import cv2
from django.http import JsonResponse
import time


def signup_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Registration successful. You can now login.')
            return redirect('login')
        else:
            messages.error(request, 'Registration failed. Please check the errors below.')
    else:
        form = UserCreationForm()

    return render(request, 'signup.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('index')
    else:
        form = AuthenticationForm()

    return render(request, 'login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.success(request, 'Logged out successfully.')
    return redirect('login')


@login_required
def index(request):
    sources = VideoSource.objects.filter(user=request.user)
    return render(request, 'index.html', {'sources': sources})


def stream_view(request, source_id):
    source = get_object_or_404(VideoSource, id=source_id)
    return render(request, 'stream_view.html', {'source': source})


"""
def video_feed(request, source_id):
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
"""


def video_feed(request, source_id):
    source = get_object_or_404(VideoSource, id=source_id)

    def generate():
        cap = cv2.VideoCapture(source.url)

        # Set min buffer to avoid delays
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or fps > 120:
            fps = 25.0  # Default MJPG
        frame_delay = 1 / fps  # Delay between two frames
        prev_time = time.time()

        while True:
            ret, frame = cap.read()
            if not ret:
                print(f"[ERROR] Stream not available: {source.url}")
                break

            # Compress frame into JPEG format
            _, buffer = cv2.imencode('.jpg', frame)

            # Send frame to buffer
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

            # Synchronize frame rate
            current_time = time.time()
            time_diff = current_time - prev_time
            if time_diff < frame_delay:
                time.sleep(frame_delay - time_diff)  # Sleep to maintain frame rate
            prev_time = time.time()  # Update the previous time

        cap.release()

    return StreamingHttpResponse(generate(), content_type='multipart/x-mixed-replace; boundary=frame')


@csrf_exempt
def start_recording_view(request, source_id):
    if request.method == 'POST':
        start_recording(source_id)
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})


@csrf_exempt
def stop_recording_view(request, source_id):
    if request.method == 'POST':
        stop_recording(source_id)

        filename = f'source_{source_id}.mp4'

        return JsonResponse({'success': True, 'filename': filename})

    return JsonResponse({'success': False})


@csrf_exempt
def add_watermark_view(request, source_id):
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
    if request.method == 'POST':
        output_url = request.POST.get('output_url')

        if not output_url:
            return JsonResponse({'success': False, 'error': 'Output URL missing'})

        success, error_message = send_recording(source_id, output_url)

        if success:
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': error_message})

    return JsonResponse({'success': False, 'error': 'Function not consented'})


def validate_rtsp_stream(url):
    cap = cv2.VideoCapture(url)
    if cap.isOpened():
        cap.release()
        return True
    cap.release()
    return False


def validate_mjpg_stream(url):
    try:
        response = requests.get(url, stream=True, timeout=5)
        content_type = response.headers.get('Content-Type', '')
        if response.status_code == 200 and 'multipart/x-mixed-replace' in content_type:
            return True
    except requests.RequestException:
        return False
    return False


def add_resource_view(request):
    if request.method == 'POST':
        try:
            try:
                data = json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError:
                return JsonResponse({'success': False, 'error': 'Invalid JSON format'})

            name = data.get('name', '').strip()
            url = data.get('url', '').strip()
            source_type = data.get('source_type', '').strip()

            if not source_type or source_type not in ['rtsp', 'mjpg']:
                return JsonResponse({'success': False, 'error': 'Invalid stream type'})

            if VideoSource.objects.filter(user=request.user, name=name).exists():
                return JsonResponse({'success': False, 'error': 'A resource with this name already exists for your '
                                                                'account'})

            if VideoSource.objects.filter(user=request.user, url=url).exists():
                return JsonResponse({'success': False, 'error': 'A resource with this URL already exists for your '
                                                                'account'})

            # Validations according to the stream type
            if source_type == 'rtsp':
                if not url.startswith('rtsp'):
                    return JsonResponse({'success': False, 'error': 'RTPS URL must start with rtsp'})
                if not validate_rtsp_stream(url):
                    return JsonResponse({'success': False, 'error': 'Invalid RTSP stream URL'})

            if source_type == 'mjpg' and not validate_mjpg_stream(url):
                return JsonResponse({'success': False, 'error': 'Invalid MJPG stream URL'})

            # Resource creating
            VideoSource.objects.create(
                user=request.user,
                name=name,
                url=url,
                source_type=source_type
            )

            return JsonResponse({'success': True})

        except Exception as e:
            traceback.print_exc()  # Print the exception on terminal
            return JsonResponse({'success': False, 'error': f'Unexpected error: {str(e)}'})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})
