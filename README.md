# Helpful Tips

L'applicazione, sviluppata con PyCharm, permette di acquisire flussi stream live di telecamere (mjpg, rtsp, mpd stream), dunque di effettuare una registrazione di questi e inviarla su un indirizzo esterno. A registrazione terminata si ha la possibilità di eseguire una fase di editing attraverso l'inclusione di un watermark di font e colore personalizzabile nell'angolo in basso a destra del video.
L'applicazione è stata implementata attraverso l'utilizzo della librearia OpenCV.

Osservazione: per i flussi mpd è stata implementata la sola funzionalità di streaming.

## Accesso

Effettuare il login mediante user admin (username: `admin`, pw: `admin`).  
Si troverà già una lista di flussi stream disponibili (mjpg). Ad ora non sono presenti flussi rtsp pubblici causa la difficoltà di ricerca dovuta a motivi di privacy e scadenza degli URL (tuttavia, una volta effettuato l'accesso, è sempre possibile aggiungerli qualora se ne disponesse). Viene fornita, alla fine di questo file, una procedure per creare uno stream rtsp in locale per testare la funzionalità dell'applicazione.

L'applicazione offre la possibilità di creare nuovi account per inserire stream personali.

## Recording

La fase di recording è facilmente guidata dall'applicazione; consiglio solo di tentare di ricaricare lo stream quando non parte correttamente.  
A registrazione terminata viene salvata una copia nella cartella `media/recordings/source_id.mp4` del progetto PyCharm.

Osservazione: per i flussi mjpg il file della registrazione potrebbe avere una durata diversa del tempo di effettiva registrazione. Gli stream mjpg non sono infatti flussi continui di frame, dunque alcuni di questi potrebbero andare persi (delay di rete, ecc...). Nel terminale di PyCharm vengono comunque specificati i frame acquisiti per ogni registrazione. Per i flussi rtsp invece lo streaming ad altissima qualità potrebbe generare delle distorsioni.

## Editing

La procedura di editing è graficamente guidata dall'app.  
Viene salvata una copia in `media/recordings/` denominata `source_id_watermarked.mp4`.

## Sending

Specificare nel form relativo un URL valido. Per testare la funzionalità, consiglio di creare un URL temporaneo su [Webhook.site](https://webhook.site/) e verificare l'upload della registrazione editata.  
Attenzione: Webhook.site rifiuta l'upload di file troppo grandi senza permessi, quindi caricare registrazioni non troppo lunghe.

-------------------------------------------------------------------------------------------------------

## Come creare un flusso rtsp continuo in locale

  1. Scaricare (se non si dispone già) [rtsp simple server](https://sourceforge.net/projects/rtspsimpleserver.mirror/). Estrarre i file dalla cartella dunque
     eseguire su cmd `mediamtx.exe`
     
  2. Scaricare (se non se ne dispone già) [ffmpeg](https://www.gyan.dev/ffmpeg/builds/) (spostarsi nella sezione "release builds" e cercare 
     `ffmpeg-release-essentials.zip`). Aggiungere ffmpeg al path delle varibili di ambiente in modo che il comando sia sempre raggiungibile da terminale.
     Eseguire su una seconda window cmd `ffmpeg -re -stream_loop -1 -i "path_persona_stream.mp4" -c:v copy -f rtsp rtsp://127.0.0.1:8554/stream`
     Osservazione: inserire il corretto numero della porte su cui rstp simple server è in ascolto per flussi rstp (viene specificato quando si esegue nell prima         window cmd `mediamtx.exe`
     
  3. Testare lo stream su VLC, andando su `media` - `open network stream` - insert `rtsp://127.0.0.1:8554/stream`
    
  4. Testare il flusso sull'applicazione

