
## *Disclaimer*

*This application has been designed solely for educational purposes. No malicious intent is hidden behind the code.*


# Helpful Tips

The application, developed with PyCharm, allows you to acquire live camera streams (mjpg, rtsp, mpd stream), enabling you to record these streams and send them to an external address. Once recording is finished, you have the option to perform an editing phase by adding a customizable watermark (font and color) in the lower right corner of the video.  
The application was implemented using the OpenCV library and ffmpeg (for the installation see the guide at the end of the document).

**Note:** For .mpd streams, only the streaming functionality has been implemented.

## Access

Log in using the admin user (username: `admin`, pw: `admin`).  
A list of available streams (mjpg) will already be provided. Currently, there are no public rtsp streams due to the difficulty in finding them because of privacy concerns and URL expiration (however, once logged in, you can add them if available). <underline> A procedure to create a local rtsp stream for testing the application's functionality is provided at the end of this file. </underline>

The application also offers the possibility to create new accounts for adding personal streams.

## Recording

The recording phase is easily guided by the application; I only recommend trying to reload the stream if it does not start correctly.  
Once recording is finished, a copy is saved in the `media/recordings/source_id.mp4` folder of the PyCharm project.

**Note:** For mjpg streams, OpenCV is used, so the recording file may have a duration different from the actual recording time. Mjpg streams are not continuous frame streams, so some frames may be lost (network delay, etc.). The PyCharm terminal still displays the number of frames captured for each recording. For rtsp streams, streaming is ensured through ffmpeg (rtsp streams in low resolution might experience slowdowns or stutters).

## Editing

The editing procedure is graphically guided by the app.  
A copy is saved in `media/recordings/` named `source_id_watermarked.mp4`.

## Sending

Enter a valid URL in the corresponding form. To test the functionality, I recommend creating a temporary URL on [Webhook.site](https://webhook.site/) and verifying the upload of the edited recording.  
**Note:** Webhook.site rejects the upload of files that are too large without permission, so upload recordings that are not too long (generally around a dozen seconds at most).

---

## How to Create a Continuous Local rtsp Stream

1. Download (if you don't already have it) [rtsp simple server](https://sourceforge.net/projects/rtspsimpleserver.mirror/). Extract the files from the folder, then run `mediamtx.exe` from the command prompt.
     
2. Download (if you don't already have it) [ffmpeg](https://www.gyan.dev/ffmpeg/builds/) (navigate to the "release builds" section and look for `ffmpeg-release-essentials.zip`). Add ffmpeg to your system's environment variables path so that the command is always accessible from the terminal.  
   Download/choose an .mp4 file to create the continuous rtsp stream.  
   In a second command prompt window, run:  
   `ffmpeg -re -stream_loop -1 -i "personal_path_videostream.mp4" -c:v copy -f rtsp rtsp://127.0.0.1:8554/stream`  
   **Note:** Enter the correct port number where the rtsp simple server is listening for rtsp streams (this is specified when you run `mediamtx.exe` in the first command prompt window).
     
4. Test the stream on VLC by going to `Media` → `Open Network Stream` and entering `rtsp://127.0.0.1:8554/stream`.
    
5. Test the stream in the application.

