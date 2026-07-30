# Universal Video Translator

[Italiano](README.md) | [English](README.en.md)

Applicazione desktop Windows per tradurre video in italiano e riprodurre una voce sintetizzata sincronizzata con le battute originali. La pipeline usa sottotitoli esistenti quando disponibili e Faster-Whisper come fallback.

> Stato: **v0.2.0 browser integration**. Supporta video locali, file SRT/VTT, URL web, riproduzione progressiva, esportazione audio/video e modalità Live PC.

## Funzioni

- URL YouTube tramite yt-dlp e cookie del browser;
- video e audio locali;
- priorità ai sottotitoli del video, con selezione automatica della lingua nativa;
- trascrizione locale con Faster-Whisper quando i sottotitoli non sono disponibili;
- traduzione italiana locale tramite Ollama;
- scelta del modello Ollama dalla GUI, con `translategemma:latest` predefinito;
- sintesi vocale Kokoro-82M con Sara e Nicola;
- fallback alle voci installate in Windows;
- buffer progressivo per iniziare la riproduzione senza attendere l’intero video;
- pulizia dei sottotitoli YouTube progressivi per evitare ripetizioni ed eco;
- coda vocale serializzata per impedire sovrapposizioni;
- player video ridimensionabile con Avvia, Pausa e Stop;
- tema scuro e menu contestuale per incollare i collegamenti;
- testo tradotto, overlay desktop e modalità Live PC;
- esportazione WAV/MP3 e creazione di un MP4 con traccia italiana;
- cache locale delle traduzioni.
- collegamento opzionale da Chrome/Edge tramite protocollo locale `uvt://`.

## Pipeline

```text
Video / YouTube / SRT / VTT
            |
            v
Sottotitoli esistenti oppure Faster-Whisper
            |
            v
Traduzione italiana con Ollama
            |
            v
Voce Kokoro o Windows
            |
            v
Player sincronizzato / esportazione audio-video
```

## Requisiti Windows

- Windows 10 o 11;
- Python 3.10 o superiore; Python 3.11+ consigliato;
- [Ollama](https://ollama.com/download/windows);
- FFmpeg completo di `ffmpeg`, `ffprobe` e `ffplay` nel PATH;
- eSpeak NG x64 per le voci Kokoro;
- spazio disponibile per dipendenze, modelli Ollama e Kokoro.

## Installazione rapida

Apri PowerShell nella cartella del progetto:

```powershell
.\INSTALL_WINDOWS.bat
.\VERIFICA_WINDOWS.bat
.\AVVIA_WINDOWS.bat
```

`INSTALL_WINDOWS.bat` crea `.venv`, installa tutte le dipendenze e scarica `translategemma:latest` tramite Ollama.

Al primo utilizzo di Kokoro viene scaricato anche il modello `hexgrad/Kokoro-82M`.

## Avvio manuale

```powershell
.\.venv\Scripts\python.exe .\universal_video_translator.py
```

Se Ollama non è già attivo:

```powershell
ollama serve
```

## Utilizzo

1. Inserisci un URL YouTube oppure seleziona un video, audio, SRT o VTT.
2. Scegli modello Ollama, lingua originale, motore e voce.
3. Premi **Avvia**.
4. Usa **Esporta audio** o **Crea video IT** per salvare il risultato.

Per YouTube lascia normalmente la lingua su `auto`. Se il sito richiede autenticazione, seleziona il browser nel quale hai effettuato l’accesso.

## Collegamento browser v0.2

1. Nell'app premi **Collega browser**. Windows registra `uvt://` soltanto per l'utente corrente e apre la cartella dell'estensione.
2. Apri `chrome://extensions` oppure `edge://extensions`.
3. Attiva **Modalità sviluppatore**, scegli **Carica estensione non pacchettizzata** e seleziona la cartella aperta dall'app.
4. Fissa l'estensione **Send to Universal Video Translator** alla barra.
5. Su una pagina video premi l'estensione. UVT scarica il contenuto, avvia la traduzione e apre automaticamente il player con la sola voce italiana.

L'estensione richiede esclusivamente `activeTab`: legge l'URL HTTP/HTTPS della scheda attiva soltanto al click. Non legge cookie, cronologia, contenuti delle pagine o altre schede e non usa servizi cloud.

## Audio automatico AI Overlay OS

All'avvio, UVT rileva e seleziona automaticamente `CABLE Output` come ingresso e abilita la voce italiana. Avviando l'Overlay, Firefox viene instradato su `CABLE Input`; Stop, errore e chiusura dell'app lo ripristinano sull'uscita Windows predefinita. Le cuffie o casse fisiche devono restare il dispositivo predefinito, così viene riprodotta soltanto la voce italiana.

Puoi comunque scegliere manualmente `Audio di sistema (predefinito)` o disabilitare la voce italiana dopo il rilevamento dei dispositivi.

Il routing usa il componente locale SoundVolumeView incluso intatto nella distribuzione. Se il componente non è disponibile, l'Overlay continua a funzionare e segnala che il routing deve essere eseguito manualmente.

## Build EXE Windows

Dopo una verifica completata:

```powershell
.\BUILD_EXE_WINDOWS.bat
```

L’applicazione viene creata in:

```text
dist\UniversalVideoTranslator\UniversalVideoTranslator.exe
```

La build è `onedir`: per distribuirla occorre comprimere e copiare **l’intera cartella** `dist\UniversalVideoTranslator`, non soltanto il file EXE.

Ollama e il modello di traduzione restano componenti esterni e devono essere disponibili sul PC che esegue l’applicazione.

## Verifica

```powershell
.\VERIFICA_WINDOWS.bat
```

La verifica controlla sintassi, test automatici, FFmpeg, eSpeak NG, Kokoro, Ollama e il modello predefinito.

Per una prova rapida usa `examples\demo.srt`. Prima di distribuire una build verifica anche un video locale e un URL YouTube.

## Dati e privacy

Traduzione, trascrizione e sintesi vocale vengono eseguite localmente. Le connessioni esterne servono per scaricare video, dipendenze e modelli. La cache delle traduzioni è salvata localmente in `.uvt-cache.json`.

## Limiti noti

- la qualità della traduzione dipende dal modello Ollama selezionato;
- il primo avvio di Kokoro richiede il download del modello;
- YouTube può richiedere cookie validi e può modificare i propri sistemi di accesso;
- velocità di preparazione e ritardo dipendono dalle prestazioni del PC;
- la v0.2.0 è una distribuzione portatile, non un installer MSI/Setup;
- dopo aver spostato la cartella portatile, premi nuovamente **Collega browser** per aggiornare il percorso registrato.

## Licenza

Distribuito con licenza [Apache 2.0](LICENSE).

## Autore

Progetto sviluppato da [dal1312](https://github.com/dal1312).
