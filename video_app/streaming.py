import cv2
import os
import time
import threading
import requests
from django.conf import settings
from .models import VideoSource, Recording

recording_processes = {}  # Dizionario per tenere traccia dei thread attivi


def record_stream(source_id, output_path, source_url, source_type, fps, width, height):
    cap = cv2.VideoCapture(source_url)

    fourcc = cv2.VideoWriter.fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    if not cap.isOpened() or not out.isOpened():
        print(f"Errore: impossibile avviare registrazione per {source_url}")
        return

    frame_count = 0

    while recording_processes.get(source_id):
        ret, frame = cap.read()
        if not ret:
            print(f"Errore: frame non disponibile per {source_url}")
            break

        out.write(frame)
        frame_count += 1

        # Solo per MJPG -> aggiungi delay artificiale
        if source_type == 'mjpg':
            time.sleep(1 / fps)

    cap.release()
    out.release()

    print(f"Registrazione terminata per {source_url} - Frames acquisiti: {frame_count}")


def start_recording(source_id):
    source = VideoSource.objects.get(id=source_id)
    output_path = os.path.join(settings.MEDIA_ROOT, 'recordings', f'source_{source.id}.mp4')

    cap = cv2.VideoCapture(source.url)

    if not cap.isOpened():
        raise ValueError(f"Errore: impossibile aprire la sorgente video {source.url}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or fps > 120:  # MJPG di solito non ha FPS, RTSP può avere valori strani
        fps = 5.0 if source.source_type == 'mjpg' else 25.0

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    cap.release()

    if width == 0 or height == 0:
        raise ValueError(f"Errore: risoluzione non valida per la sorgente {source.url}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    recording_processes[source_id] = True

    # Avvia un thread per la registrazione
    thread = threading.Thread(
        target=record_stream,
        args=(source_id, output_path, source.url, source.source_type, fps, width, height),
    )
    thread.start()


def stop_recording(source_id):
    if source_id in recording_processes:
        recording_processes[source_id] = False

    output_path = os.path.join(settings.MEDIA_ROOT, 'recordings', f'source_{source_id}.mp4')

    source = VideoSource.objects.get(id=source_id)
    recording = Recording.objects.create(source=source, file=f'recordings/source_{source_id}.mp4')
    recording.save()

    print(f"Registrazione salvata: {output_path}")


def add_watermark_and_save(source_id, text, color, font_scale):
    try:
        recording = Recording.objects.filter(source_id=source_id).latest('created_at')
        input_path = recording.file.path
        output_path = input_path.replace('.mp4', '_watermarked.mp4')

        cap = cv2.VideoCapture(input_path)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

        fourcc = cv2.VideoWriter.fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        # font_scale = 1.5
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

            # Applica watermark in basso a destra
            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness)[0]
            text_x = width - text_size[0] - 20
            text_y = height - 20

            # Ombra nera
            cv2.putText(frame, text, (text_x + 2, text_y + 2), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), font_thickness + 2, cv2.LINE_AA)

            # Testo con colore personalizzato
            cv2.putText(frame, text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color_bgr, font_thickness, cv2.LINE_AA)

            out.write(frame)

        cap.release()
        out.release()

        recording.file.name = os.path.join('recordings', os.path.basename(output_path))
        recording.save()

        print(f"Watermark applied successfully. Processed {frame_count} frames.")

    except Exception as e:
        print(f"Error applying watermark: {e}")


def send_recording(source_id, output_url):
    """
    Invia il video registrato al server esterno tramite POST multipart/form-data.
    Ritorna (successo, messaggio di errore)
    """
    try:
        recording = Recording.objects.filter(source_id=source_id).latest('created_at')

        if not recording.file:
            return False, "File non trovato"

        with open(recording.file.path, 'rb') as f:
            response = requests.post(output_url, files={'file': f}, timeout=20)

        if response.status_code in [200, 201, 202]:
            return True, None
        else:
            return False, f"Errore nell'invio: {response.status_code} - {response.text}"

    except Recording.DoesNotExist:
        return False, "Registrazione non trovata"

    except Exception as e:
        return False, f"Errore generico: {str(e)}"

