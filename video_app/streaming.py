import cv2
import os
import time
import threading
import requests
from django.conf import settings
from .models import VideoSource, Recording
import subprocess

recording_processes = {}  # Dictionary to keeping track active threads for recording


def record_stream(source_id, output_path, source_url, source_type, fps, width, height):
    # If the source is RTSP, record with FFmpeg directly.
    if source_type == 'rtsp':
        command = [
            'ffmpeg',
            '-rtsp_transport', 'tcp',  # force ffmpeg to use TCP for RTSP (more reliable)
            '-i', source_url,
            '-c', 'copy',  # uses stream copy mode to record the stream without re-encoding, preserving the quality
            '-movflags', '+faststart+frag_keyframe+empty_moov',  # can help create a fragmented MP4 that’s more
            # tolerant of an abrupt stop
            output_path
        ]
        print(f"Starting FFmpeg recording for {source_url}")

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE  # Enable sending commands to ffmpeg
        )

        try:
            # Poll until the recording flag is turned off
            while recording_processes.get(source_id):
                time.sleep(1)  # Check every second; adjust sleep as needed
        except Exception as e:
            print(f"Error during FFmpeg recording: {e}")
        finally:
            # Instead of sending SIGINT, send 'q' via stdin for a graceful shutdown
            if process.stdin:
                process.stdin.write(b"q\n")  # graceful way to instruct FFmpeg to stop recording
                process.stdin.flush()  # ensures the command is sent immediately
            process.wait()  # Wait for the process to terminate

            # debugger test
            stderr = process.stderr.read().decode('utf-8', errors='ignore')
            # if stderr:
            #    print(f"FFmpeg stderr: {stderr}")

            print(f"Recording terminated for {source_url} using FFmpeg (RTSP).")
    else:
        # Otherwise, use OpenCV for recording (MJPEG or similar streams)
        cap = cv2.VideoCapture(source_url)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)

        fourcc = cv2.VideoWriter.fourcc(*'mp4v')  # codec configuration for .mp4 files
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        if not cap.isOpened() or not out.isOpened():
            print(f"Error: impossible starting recording for {source_url}")
            return

        frame_count = 0
        prev_time = time.time()

        while recording_processes.get(source_id):
            ret, frame = cap.read()  # ret is a boolean that returns True if the frame is available
                                     # frame is the image frame
            if not ret:
                print(f"Error: frame not available for {source_url}")
                break

            out.write(frame)
            frame_count += 1

            current_time = time.time()
            time_diff = current_time - prev_time
            if time_diff < (1 / fps):
                time.sleep((1 / fps) - time_diff)  # Sleep to maintain the correct frame rate
            prev_time = time.time()

            if source_type == 'mjpg':
                time.sleep(0.002)  # Small sleep to avoid CPU overloads in case of high FPS

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
        fps = 25  # default fps if the original is too low or too high

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
        recording = Recording.objects.filter(source_id=source_id).latest('created_at')  # retrieve the last recording
        input_path = recording.file.path  # retrieve the path of the last recording
        output_path = input_path.replace('.mp4', '_watermarked.mp4')  # construct the output path by replacing the
        # .mp4 extension with '_watermarked.mp4'

        cap = cv2.VideoCapture(input_path)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)

        fourcc = cv2.VideoWriter.fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        font_thickness = 2

        # nested function to convert hexadecimal color to BGR
        def hex_to_bgr(hex_color):
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
            return b, g, r  # OpenCV uses BGR order instead of the more common RGB, so the function returns (b, g, r)

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
            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness)[0] # compute text
            # size
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
            response = requests.post(output_url, files={'file': f}, timeout=20)  # use a request to send the file

        if response.status_code in [200, 201, 202]:
            return True, None
        else:
            return False, f"Sending error: {response.status_code} - {response.text}"

    except Recording.DoesNotExist:
        return False, "Recording not found"

    except Exception as e:
        return False, f"Generic error: {str(e)}"
