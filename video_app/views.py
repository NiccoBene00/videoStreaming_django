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
import subprocess
import xml.etree.ElementTree as ET


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


# OpencCV for MJPEG and ffmpeg for RTSP
def video_feed(request, source_id):
    source = get_object_or_404(VideoSource, id=source_id)

    if source.source_type == 'mpd':
        return JsonResponse({'mpd_url': source.url})  # MPEG-DASH managed differently (external player)

    def generate_opencv():

        print("Opening stream with OpenCV...")

        cap = cv2.VideoCapture(source.url)

        # Set min buffer to avoid delays
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # this minimizes delay by limiting how many frames are preloaded
        # before processing.

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
            _, buffer = cv2.imencode('.jpg', frame)  # imencode return a tuple, the first element (boolean) is ignored

            # Send frame to buffer
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')  # This format is commonly used to
            # stream video frames to a web browser

            # Retrieves the current time and calculates the time difference (time_diff) since the last frame was
            # processed. This helps determine if the function needs to wait to maintain the desired frame rate.
            current_time = time.time()
            time_diff = current_time - prev_time
            if time_diff < frame_delay:
                time.sleep(frame_delay - time_diff)  # Sleep to maintain frame rate
            prev_time = time.time()  # Update the previous time

        cap.release()

    def generate_ffmpeg():

        print("Opening RTSP stream with FFmpeg...")

        command = [
            'ffmpeg',
            '-i', source.url,
            '-f', 'mjpeg',  # sets the output format to MJPEG (stream of JPEG images)
            '-q:v', '5',  # standard video quality
            '-r', '30',  # set the frame rate to 30 fps
            '-loglevel', 'quiet',  # suppresses FFmpeg's log output to keep the console output clean
            '-'
        ]

        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        data = b""  # data is initialized as an empty byte string. This buffer will accumulate chunks of binary data
        # read from FFmpeg’s stdout until a complete JPEG frame is detected.

        try:
            while True:
                # Read a chunk of data from FFmpeg's stdout
                chunk = process.stdout.read(1024)
                if not chunk:
                    break
                data += chunk  # This buffer accumulates raw binary data until a full JPEG frame is detected.

                # Search for JPEG start and end markers
                start = data.find(b'\xff\xd8')
                end = data.find(b'\xff\xd9')

                if start != -1 and end != -1 and end > start:  # check if both markers are found and the end marker is
                    # after the start marker
                    # Extract the JPEG frame from the data buffer
                    frame = data[start:end + 2]  # remember that the end marker is 2 bytes long

                    #  After extracting the frame, the buffer is updated by removing the bytes corresponding to the
                    #  extracted frame. This ensures that the next iteration works with any remaining data that might
                    #  contain the beginning of a subsequent frame.
                    data = data[end + 2:]

                    # The function yields the extracted frame formatted as a multipart HTTP response
                    yield (
                            b'--frame\r\n'
                            b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
                    )
        except Exception as e:
            print(f"Error during stream: {e}")
        finally:
            process.stdout.close()
            process.stderr.close()
            process.terminate()
            process.wait()

    # MJPG → OpenCV, RTSP → FFmpeg
    if source.source_type == "rtsp":
        return StreamingHttpResponse(generate_ffmpeg(), content_type='multipart/x-mixed-replace; boundary=frame')
    else:
        # Since MJPEG streams provide a sequence of JPEG images, OpenCV can efficiently decode and handle these images
        # for real-time analysis and display.
        return StreamingHttpResponse(generate_opencv(), content_type='multipart/x-mixed-replace; boundary=frame')


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
        print("RTSP stream is valid")
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


def validate_mpd_stream(url):
    try:
        # Try to make e request to the mpd URL
        response = requests.get(url, timeout=5)

        # Check if the response is valid
        if response.status_code != 200:
            return False

        # Check if the content type is valid
        content_type = response.headers.get('Content-Type', '')
        if 'application/dash+xml' not in content_type and 'text/xml' not in content_type:
            return False

        # Check if the response is a valid XML file
        try:
            root = ET.fromstring(response.text)
            if root.tag.endswith("MPD"):  # Check if the root tag is MPD
                return True
        except ET.ParseError:
            return False

    except requests.RequestException:
        return False

    return False


def add_resource_view(request):
    if request.method == 'POST':
        try:
            try:
                data = json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError:
                return JsonResponse({'success': False, 'error': 'JSON data not valid'})

            name = data.get('name', '').strip()
            url = data.get('url', '').strip()
            source_type = data.get('source_type', '').strip()

            if source_type not in ['rtsp', 'mjpg', 'mpd']:
                return JsonResponse({'success': False, 'error': 'Invalid stream type'})

            if VideoSource.objects.filter(user=request.user, name=name).exists():
                return JsonResponse(
                    {'success': False, 'error': 'A resource with this name already exists for your account'})

            if VideoSource.objects.filter(user=request.user, url=url).exists():
                return JsonResponse(
                    {'success': False, 'error': 'A resource with this URL already exists for your account'})

            # Specific checks for each stream type
            if source_type == 'rtsp':
                if not url.startswith('rtsp'):
                    return JsonResponse({'success': False, 'error': 'L\'URL for rtsp stream must start with "rtsp://"'})
                if not validate_rtsp_stream(url):
                    return JsonResponse({'success': False, 'error': 'Invalid RTSP stream'})

            elif source_type == 'mjpg' and not validate_mjpg_stream(url):
                return JsonResponse({'success': False, 'error': 'Invalid MJPEG stream'})

            elif source_type == 'mpd' and not url.endswith('.mpd'):
                return JsonResponse({'success': False, 'error': 'L\'URL for mpd stream must end with ".mpd"'})

            elif source_type == 'mpd' and not validate_mpd_stream(url):
                return JsonResponse({'success': False, 'error': 'Invalid MPD stream URL'})

            # Resource creation
            VideoSource.objects.create(
                user=request.user,
                name=name,
                url=url,
                source_type=source_type
            )

            return JsonResponse({'success': True})

        except Exception as e:
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': f'Unexpected error: {str(e)}'})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})


def remove_resource_view(request):
    if request.method == 'POST':
        try:
            # Parse the JSON payload from the request body
            try:
                data = json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError:
                return JsonResponse({'success': False, 'error': 'JSON data not valid'})

            # Get the stream name from the data and perform basic validation
            name = data.get('name', '').strip()

            if not name:
                return JsonResponse({'success': False, 'error': 'Stream name is required'})

            # Verify that a VideoSource with the given name exists for the current user
            try:
                video_source = VideoSource.objects.get(user=request.user, name=name)
            except VideoSource.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Stream resource not found. Remember that the system is'
                                                                ' case sensitive.'})

            # Delete the resource and return a success message
            video_source.delete()
            return JsonResponse({'success': True})

        except Exception as e:
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': f'Unexpected error: {str(e)}'})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})
