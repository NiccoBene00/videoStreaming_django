import concurrent.futures
import cv2
import os
import time
import threading
import requests
from django.conf import settings
from .models import VideoSource, Recording

recording_processes = {}  # Dictionary to keeping track active threads

"""
def record_stream(source_id, output_path, source_url, source_type, fps, width, height):
    cap = cv2.VideoCapture(source_url)

    fourcc = cv2.VideoWriter.fourcc(*'mp4v')  # codec configurations for .mp4 files
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    if not cap.isOpened() or not out.isOpened():
        print(f"Error: impossible starting recording for {source_url}")
        return

    frame_count = 0

    while recording_processes.get(source_id):
        ret, frame = cap.read()
        if not ret:
            print(f"Error: frame not available for {source_url}")
            break

        out.write(frame)
        frame_count += 1

        # Only for mjpg -> add artificial delay
        if source_type == 'mjpg':
            time.sleep(1 / fps)

    cap.release()
    out.release()

    print(f"Recording terminated for {source_url} - Frames acquired: {frame_count}")
"""

# Capture the video frames in order to store them in .mp4 file as long as the recording is active
def record_stream(source_id, output_path, source_url, source_type, fps, width, height):
    cap = cv2.VideoCapture(source_url)

    fourcc = cv2.VideoWriter.fourcc(*'mp4v')  # codec configurations for .mp4 files
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    if not cap.isOpened() or not out.isOpened():
        print(f"Error: impossible starting recording for {source_url}")
        return

    frame_count = 0
    prev_time = time.time()

    while recording_processes.get(source_id):
        ret, frame = cap.read()
        if not ret:
            print(f"Error: frame not available for {source_url}")
            break

        # Write the current frame to the output file
        out.write(frame)
        frame_count += 1

        # Calculate the time difference
        current_time = time.time()
        time_diff = current_time - prev_time

        # Synchronize based on frame rate
        if time_diff < (1 / fps):
            time.sleep((1 / fps) - time_diff)  # Sleep to maintain the correct frame rate

        prev_time = time.time()  # Update the previous time

        # Only for MJPEG streams, ensure artificial delay (frame rate control)
        if source_type == 'mjpg':
            time.sleep(0.001)  # Small sleep to avoid CPU overload in case of high FPS

    cap.release()
    out.release()

    print(f"Recording terminated for {source_url} - Frames acquired: {frame_count}")


# Initialize the recording, check source state and start a parallel tread for starting recording
def start_recording(source_id):
    source = VideoSource.objects.get(id=source_id)  # retrieve source from db
    output_path = os.path.join(settings.MEDIA_ROOT, 'recordings', f'source_{source.id}.mp4')

    cap = cv2.VideoCapture(source.url)  # open the stream

    if not cap.isOpened():
        raise ValueError(f"Error: opening impossible for source {source.url}")

    fps = cap.get(cv2.CAP_PROP_FPS)  # retrieve video fps (some streams may not have a standard fps)
    if fps <= 0 or fps > 120:
        fps = 5.0 if source.source_type == 'mjpg' else 25.0  # default fps if the original is too low or too high
        # for MJPG: default fps:5
        # for RTSP: default fps:25

    # Retrieve video resolution to check for errors
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    cap.release()

    if width == 0 or height == 0:
        raise ValueError(f"Error: resolutions not valid for source {source.url}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    recording_processes[source_id] = True  # start recording flag

    # Start thread for recording
    thread = threading.Thread(
        target=record_stream,
        args=(source_id, output_path, source.url, source.source_type, fps, width, height),
    )
    thread.start()  # start parallel recording thread


def stop_recording(source_id):
    if source_id in recording_processes:
        recording_processes[source_id] = False

    output_path = os.path.join(settings.MEDIA_ROOT, 'recordings', f'source_{source_id}.mp4')

    source = VideoSource.objects.get(id=source_id)
    recording = Recording.objects.create(source=source, file=f'recordings/source_{source_id}.mp4')
    recording.save()

    print(f"Recording stored: {output_path}")


def add_watermark_and_save(source_id, text, color, font_scale):
    try:
        recording = Recording.objects.filter(source_id=source_id).latest('created_at')
        input_path = recording.file.path
        output_path = input_path.replace('.mp4', '_watermarked.mp4')

        cap = cv2.VideoCapture(input_path)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)

        fourcc = cv2.VideoWriter.fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        font_thickness = 2

        def hex_to_bgr(hex_color):
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
            return b, g, r

        color_bgr = hex_to_bgr(color)

        print(f"Applying watermark: '{text}' to {input_path}")
        print(f"Output path: {output_path}")
        print(f"Video size: {width}x{height}, FPS: {fps}")

        frame_count = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1

            # Apply watermark bottom right
            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness)[0]
            text_x = width - text_size[0] - 20
            text_y = height - 20

            # Black shadow
            cv2.putText(frame, text, (text_x + 2, text_y + 2), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0),
                        font_thickness + 2, cv2.LINE_AA)

            # Text with customized color
            cv2.putText(frame, text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color_bgr, font_thickness,
                        cv2.LINE_AA)

            out.write(frame)

        cap.release()
        out.release()

        recording.file.name = os.path.join('recordings', os.path.basename(output_path))
        recording.save()

        print(f"Watermark applied successfully. Processed {frame_count} frames.")

    except Exception as e:
        print(f"Error applying watermark: {e}")


def send_recording(source_id, output_url):
    try:
        recording = Recording.objects.filter(source_id=source_id).latest('created_at')

        if not recording.file:
            return False, "File not found"

        with open(recording.file.path, 'rb') as f:
            response = requests.post(output_url, files={'file': f}, timeout=20)

        if response.status_code in [200, 201, 202]:
            return True, None
        else:
            return False, f"Sending error: {response.status_code} - {response.text}"

    except Recording.DoesNotExist:
        return False, "Recording not found"

    except Exception as e:
        return False, f"Generic error: {str(e)}"
