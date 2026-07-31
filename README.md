# Universal Video Translator

[Italiano](README.md) | [English](README.en.md)

Applicazione desktop Windows per tradurre video in italiano e riprodurre una voce sintetizzata sincronizzata con le battute originali. La pipeline usa sottotitoli esistenti quando disponibili e Faster-Whisper come fallback.

> Stato: **v0.2.1 browser integration**. L'estensione avvia esclusivamente AI Overlay OS senza leggere il link; la modalità Video e file resta disponibile manualmente nell'app.

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
- cache locale delle traduzioni;
- impostazioni persistenti, diagnostica rotante e recupero del routing audio in `%LOCALAPPDATA%\UniversalVideoTranslator`;
- singola istanza desktop: i click successivi dell'estensione vengono inoltrati alla finestra già aperta;
- avvio diretto di AI Overlay OS da Chrome/Edge tramite protocollo locale `uvt://`, senza trasferire l'URL.

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
- [Deno](https://deno.com/) per i link YouTube;
- [VB-Cable](https://vb-audio.com/Cable/) per l'avvio automatico AI Overlay OS dal browser;
- spazio disponibile per dipendenze, modelli Ollama e Kokoro.

## Installazione rapida

Apri PowerShell nella cartella del progetto:

```powershell
.\INSTALL_WINDOWS.bat
.\VERIFICA_WINDOWS.bat
.\AVVIA_WINDOWS.bat
```

`INSTALL_WINDOWS.bat` crea `.venv` e installa le dipendenze usando vincoli di versione verificati. Non modifica il Python globale e interrompe immediatamente l'installazione in caso di errore. Per scaricare anche il modello esegui `scripts\windows\Install-Windows.ps1 -PullModel`.

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
4. Fissa l'estensione **Start UVT AI Overlay** alla barra.
5. Avvia il video nel browser e premi l'estensione. La pagina e il video restano aperti; UVT seleziona **AI Overlay OS**, instrada l'audio del browser tramite VB-Cable e avvia automaticamente la traduzione in tempo reale.

> Comportamento atteso v0.2.1: il click non compila **Video e file**, non avvia yt-dlp e non scarica il video. Se compare un URL nell'app, è ancora attiva una versione precedente dell'estensione.

L'estensione **non legge e non trasmette l'URL** e non richiede alcun permesso browser: non dispone di permessi sui siti, content script, cookie, cronologia o altre schede e non usa servizi cloud. Apre una scheda locale attiva per rendere visibile la conferma del protocollo; Chrome o Edge possono lasciarla aperta e in tal caso puoi chiuderla normalmente. Ogni click genera una richiesta monouso contenente soltanto browser, orario e ID casuale: richieste duplicate, già elaborate o non recenti vengono ignorate senza aprire UVT. Se UVT è già aperto, una connessione locale autenticata inoltra la richiesta alla stessa finestra senza creare processi Overlay concorrenti. Il browser dichiarato dall'estensione viene usato esclusivamente per il routing audio Overlay. I piccoli marker anti-replay in `%LOCALAPPDATA%\UniversalVideoTranslator\browser-requests` non contengono URL; quelli scaduti vengono eliminati al successivo utilizzo dell'estensione.

`uvt://` è un'integrazione locale di Windows, non un canale autenticato crittograficamente. Conferma l'apertura del protocollo soltanto da browser e applicazioni attendibili.

## Audio automatico AI Overlay OS

All'avvio, UVT rileva e seleziona automaticamente `CABLE Output` come ingresso e abilita la voce italiana. Il click sull'estensione attende questo rilevamento e avvia l'Overlay senza compilare il campo **Video e file**. Se VB-Cable non viene rilevato, l'avvio automatico viene annullato invece di catturare l'audio di sistema. Il browser che ha aperto UVT viene instradato su `CABLE Input`; Stop, errore e chiusura dell'app lo ripristinano sull'uscita Windows predefinita. Prima del routing viene salvato un lease locale: dopo crash o chiusura forzata, UVT tenta il recupero automatico al successivo avvio. Se UVT è stato aperto manualmente, viene usato il browser scelto nella nuova impostazione avanzata **Browser audio Overlay**, separata dai cookie YouTube. Le cuffie o casse fisiche devono restare il dispositivo predefinito, così viene riprodotta soltanto la voce italiana.

Puoi comunque scegliere manualmente `Audio di sistema (predefinito)` o disabilitare la voce italiana dopo il rilevamento dei dispositivi.

Il routing usa il componente locale SoundVolumeView incluso intatto nella distribuzione. Se il componente non è disponibile, l'avvio automatico da estensione viene annullato; l'avvio manuale resta disponibile e segnala che il routing deve essere eseguito manualmente.

### Aggiornamento e controllo rapido

Dopo ogni aggiornamento dell'app:

1. Apri `chrome://extensions` oppure `edge://extensions`.
2. Premi **Ricarica** su **Start UVT AI Overlay**.
3. Verifica che l'estensione caricata punti alla cartella della build corrente:

```text
UniversalVideoTranslator\_internal\browser_extension
```

Se il click inserisce ancora un link in **Video e file**, rimuovi la vecchia estensione e carica nuovamente questa cartella. Se UVT non parte, premi ancora **Collega browser** per aggiornare il percorso `uvt://`. Se compare `VB-Cable non rilevato`, verifica che `CABLE Output (VB-Audio Virtual Cable)` sia presente nei dispositivi di registrazione di Windows: per sicurezza l'avvio automatico resta disattivato finché il dispositivo non è disponibile.

## Build EXE Windows

Dopo una verifica completata:

```powershell
.\BUILD_EXE_WINDOWS.bat
```

Il comando standard crea una release ufficiale soltanto da un worktree pulito con tag `v0.2.1`. Per un pacchetto locale di collaudo da modifiche non ancora committate usa esplicitamente `\.\BUILD_EXE_WINDOWS.bat -AllowDirty`; la provenienza registrerà `dirty: true`.

La pipeline esegue preflight, test, build PyInstaller, controllo risorse e checksum. L'applicazione viene creata in:

```text
dist-browser-v0.2-release\UniversalVideoTranslator\UniversalVideoTranslator.exe
```

La release portatile completa viene creata in `release\UniversalVideoTranslator-0.2.1-windows-x86_64.zip`, insieme al checksum `.zip.sha256`. Il pacchetto contiene README, changelog, licenze, provenienza e `SHA256SUMS.txt`; non distribuire soltanto il file EXE.

Ollama e il modello di traduzione restano componenti esterni e devono essere disponibili sul PC che esegue l’applicazione.

## Verifica

```powershell
.\VERIFICA_WINDOWS.bat
```

La verifica è non mutante e controlla sintassi, test automatici, versioni, dipendenze Python, FFmpeg/ffprobe/ffplay, Deno, SoundVolumeView, eSpeak NG, Kokoro, Faster-Whisper, SoundCard, Ollama, modello predefinito e VB-Cable.

Per una prova rapida usa `examples\demo.srt`. Prima di distribuire una build verifica anche un video locale e un URL YouTube.

## Dati e privacy

Traduzione, trascrizione e sintesi vocale vengono eseguite localmente. Le connessioni esterne servono per scaricare video, dipendenze e modelli. Impostazioni, cache, log diagnostici rotanti e stato di recupero sono salvati in `%LOCALAPPDATA%\UniversalVideoTranslator`. I log registrano eventi tecnici e tipi di errore, ma non URL, trascrizioni, traduzioni, cookie o nomi dei dispositivi. Il file principale è `logs\uvt.log`.

## Ripristino e diagnostica

- dopo una chiusura forzata, riavvia UVT: un lease persistente tenta di riportare il browser all'uscita Windows predefinita prima di accettare un nuovo Overlay;
- se un problema persiste, consulta `%LOCALAPPDATA%\UniversalVideoTranslator\logs\uvt.log`;
- per azzerare le preferenze chiudi UVT e rinomina `settings.json`; per azzerare soltanto la cache elimina `cache\translations-v1.json`;
- una seconda apertura dell'app o un nuovo click dell'estensione riusa la singola istanza già attiva.

## Limiti noti

- la qualità della traduzione dipende dal modello Ollama selezionato;
- il primo avvio di Kokoro richiede il download del modello;
- YouTube può richiedere cookie validi e può modificare i propri sistemi di accesso;
- velocità di preparazione e ritardo dipendono dalle prestazioni del PC;
- la v0.2.1 è una distribuzione portatile, non un installer MSI/Setup;
- dopo aver spostato la cartella portatile, premi nuovamente **Collega browser** per aggiornare il percorso registrato.

## Licenza

Distribuito con licenza [Apache 2.0](LICENSE).

## Autore

Progetto sviluppato da [dal1312](https://github.com/dal1312).
