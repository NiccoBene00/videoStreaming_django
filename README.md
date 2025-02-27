# Helpful Tips

L'applicazione, sviluppata con PyCharm, permette di acquisire flussi stream live di telecamere (mjpg, rtsp, mpd stream), dunque di effettuare una registrazione di questi e inviarla su un indirizzo esterno, dopo avere la possibilità di eseguire una fase di editing attraverso l'inclusione di un watermark di font e colore personalizzabile nell'angolo in basso a destra.

Osservazione: per i flussi mpd è stata implementata la sola funzionalità di streaming.

## Accesso

Effettuare il login mediante user admin (username: "admin", pw: "admin").  
Si troverà già una lista di flussi stream disponibili (mjpg). Ad ora non sono presenti flussi rtsp pubblici causa la difficoltà di ricerca dovuta a motivi di privacy e scadenza degli URL (tuttavia, una volta effettuato l'accesso, è sempre possibile aggiungerli qualora se ne disponesse).

L'applicazione offre la possibilità di creare nuovi account per inserire stream personali.

## Recording

La fase di recording è facilmente guidata dall'applicazione; consiglio solo di tentare di ricaricare lo stream quando non parte correttamente.  
A registrazione terminata viene salvata una copia nella cartella `media/recordings/source_id.mp4` del progetto PyCharm.

Osservazione: per i flussi mjpg il file della registrazione potrebbe avere una durata diversa del tempo di effettiva registrazione. Gli stream mjpg non sono infatti flussi continui di frame, dunque 
              alcuni di questi potrebbero andare persi (delay di rete, ecc...). Nel terminale di PyCharm vengono comunque specificati i frame acquisiti per ogni registrazione.

## Editing

La procedura di editing è graficamente guidata dall'app.  
Viene salvata una copia in `media/recordings/` denominata `source_id_watermarked.mp4`.

## Sending

Specificare nel form relativo un URL valido. Per testare la funzionalità, consiglio di creare un URL temporaneo su [Webhook.site](https://webhook.site/) e verificare l'upload della registrazione editata.  
Attenzione: Webhook.site rifiuta l'upload di file troppo grandi senza permessi, quindi caricare registrazioni non troppo lunghe.
