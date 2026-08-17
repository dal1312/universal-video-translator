# Universal Video Translator

[Italiano](README.md) | [English](README.en.md)

Universal Video Translator e' un'app desktop Windows per tradurre contenuti video in italiano, creare una voce sintetizzata sincronizzata e tradurre in tempo reale l'audio riprodotto dal browser tramite **AI Overlay OS**.

La versione **v0.2.1** introduce l'integrazione browser sicura: l'estensione non legge il link della pagina, non invia URL all'app e avvia solo AI Overlay OS. La modalita' **Video e file** resta disponibile manualmente per URL YouTube, video locali, audio, SRT e VTT.

### Build locale di collaudo

La build locale Windows piu' recente e' disponibile nella cartella
`dist-local-20260817\\UniversalVideoTranslator`. Avviare
`UniversalVideoTranslator.exe` direttamente da quella cartella. Questa build
non e' una release GitHub ufficiale e serve per la verifica locale di audio,
player, download YouTube e sottotitoli.

## Stato Del Progetto

- Versione corrente: `0.2.1`.
- Piattaforma target: Windows 10/11 x64.
- Distribuzione consigliata: ZIP portatile generato dalla pipeline di release.
- Elaborazione: locale, con Ollama o Argos, Faster-Whisper e voci neurali Kokoro.
- Browser supportati dall'estensione: Chrome, Edge e Firefox 121+ in modalita' unpacked/temporanea.

## Funzionalita'

- Traduzione italiana di video locali, audio, sottotitoli SRT/VTT e URL supportati da yt-dlp.
- Download YouTube con controllo Deno, limite qualita' 720p e avanzamento visibile.
- Uso prioritario dei sottotitoli esistenti; fallback locale con Faster-Whisper.
- Traduzione locale tramite Ollama, con `translategemma:latest` come modello predefinito, oppure Argos Translate offline gratuito.
- Sintesi vocale neurale Kokoro-82M con Sara e Nicola e coda anti-sovrapposizione.
- Player progressivo con video ridimensionabile, pausa, stop e audio italiano senza traccia originale in sottofondo.
- Esportazione audio WAV/MP3 e creazione MP4 con traccia italiana.
- AI Overlay OS per tradurre in tempo reale l'audio del browser.
- Routing automatico Chrome/Edge/Firefox verso VB-Cable con ripristino crash-safe.
- Singola istanza desktop con inoltro locale autenticato dei click successivi dell'estensione.
- Impostazioni, cache, log e stato di recupero in `%LOCALAPPDATA%\UniversalVideoTranslator`.
- Build Windows riproducibile con ZIP, checksum, provenienza e licenze.

Il piano operativo per lo sviluppo e le verifiche locali è in
[`docs/PROGETTO_SVILUPPO.md`](docs/PROGETTO_SVILUPPO.md). I workflow GitHub
restano manuali durante questa fase e non eseguono test automatici a ogni push.

## Modalita' Operative

### Video e file

Usa questa modalita' quando vuoi elaborare un file o un link manualmente.

1. Inserisci un URL YouTube/supportato oppure seleziona un file video, audio, SRT o VTT.
2. Scegli modello Ollama, lingua sorgente, motore voce e voce.
3. Premi **Avvia**.
4. Riproduci il risultato oppure esporta audio/video.

Per YouTube lascia normalmente la lingua su `auto`. Se il video richiede autenticazione, seleziona nelle impostazioni avanzate il browser in cui hai gia' effettuato l'accesso.

### AI Overlay OS

Usa questa modalita' per tradurre in tempo reale cio' che senti nel browser.

1. Installa VB-Cable.
2. Avvia UVT.
3. UVT rileva `CABLE Output` e abilita la voce italiana.
4. Premi l'estensione nel browser oppure avvia manualmente **AI Overlay OS**.
5. Il browser viene instradato su `CABLE Input`; le casse/cuffie restano come uscita predefinita Windows.

Scegli il profilo **Rapido**, **Bilanciato** o **Qualita** in base al compromesso desiderato. Lo streaming usa segmentazione vocale basata su pause (VAD), produce trascrizioni/traduzioni incrementali e riduce automaticamente il volume originale durante la voce italiana. La sincronizzazione adattiva regola gradualmente la velocità della voce per recuperare lo scarto senza variazioni brusche. Il pannello Live mostra la latenza sintetica; la diagnostica completa resta disponibile su richiesta.

Se VB-Cable non viene rilevato, l'avvio automatico da estensione viene bloccato per evitare di catturare l'audio di sistema sbagliato.

## Pipeline

```text
Video / YouTube / SRT / VTT
        |
        v
Sottotitoli esistenti o Faster-Whisper
        |
        v
Traduzione italiana con Ollama
        |
        v
Voce Kokoro
        |
        v
Player sincronizzato o esportazione
```

Per AI Overlay OS la pipeline lavora in modo incrementale: VAD rileva parlato e pause, Whisper elabora subito ciascun segmento e le code a capacita' limitata scartano i dati vecchi quando il sistema resta indietro.

## Requisiti Windows

- Windows 10 o Windows 11 x64.
- Python 3.10 x64 per l'esecuzione da sorgente.
- [Ollama](https://ollama.com/download/windows) con modello `translategemma:latest` o compatibile.
- FFmpeg completo di `ffmpeg`, `ffprobe` e `ffplay`.
- [Deno](https://deno.com/) per i link YouTube.
- [VB-Cable](https://vb-audio.com/Cable/) per l'avvio automatico AI Overlay OS dal browser.
- eSpeak NG x64 o dati eSpeak inclusi nella build per Kokoro.
- Spazio disco sufficiente per modelli e dipendenze locali.

## Installazione Da Sorgente

Apri PowerShell nella cartella del progetto ed esegui:

```powershell
.\INSTALL_WINDOWS.bat
.\VERIFICA_WINDOWS.bat
.\AVVIA_WINDOWS.bat
```

L'installazione cerca Python x64 3.10 prima tramite `py -3.10` e poi tramite
`python`, crea sempre la `.venv`, applica vincoli verificati e termina al primo
errore. Non modifica il Python globale. Se il runtime manca, mostra direttamente
il comando `winget install Python.Python.3.10`.

Per scaricare anche il modello predefinito:

```powershell
scripts\windows\Install-Windows.ps1 -PullModel
```

### Motori gratuiti opzionali

Argos traduce interamente offline senza Ollama. Per la sintesi vocale è
supportato esclusivamente Kokoro:

```powershell
.\INSTALLA_MOTORI_OPZIONALI_WINDOWS.bat -Argos -AcceptModelLicenses
.\INSTALLA_MOTORI_OPZIONALI_WINDOWS.bat -Kokoro
```

`-Kokoro` installa il runtime Kokoro nell'ambiente `.venv`; il modello
Kokoro-82M viene scaricato automaticamente al primo utilizzo e resta nella
cache locale di Hugging Face.

Senza parametri lo script prepara Argos. I dati vengono salvati in
`%LOCALAPPDATA%\UniversalVideoTranslator`.

### Più interlocutori nei media

Per i video con due o più persone, abilita **Separa automaticamente le voci**
nelle impostazioni avanzate. Il progetto mantiene le battute separate, assegna
un'etichetta a ciascun interlocutore e può usare una voce TTS diversa per i
primi due speaker. La funzione è opzionale e non modifica i file SRT/VTT.

Il motore di diarizzazione è separato dal percorso base Windows. Per abilitarlo
in un ambiente dedicato:

```powershell
pip install -e ".[diarization]"
$env:UVT_HF_TOKEN = "<token Hugging Face>"
```

La diarizzazione è più adatta ai file già registrati; in modalità live può
aumentare la latenza. Se il modello non è installato, la trascrizione standard
continua a funzionare senza etichette.

## Avvio Manuale

```powershell
.\.venv\Scripts\python.exe .\universal_video_translator.py
```

Se Ollama non e' gia' attivo:

```powershell
ollama serve
```

## Collegamento Browser

1. Premi **Collega browser** nell'app.
2. Windows registra `uvt://` solo per l'utente corrente.
3. L'app apre la cartella dell'estensione inclusa nella build.
4. Apri `chrome://extensions`, `edge://extensions` oppure `about:debugging#/runtime/this-firefox`.
5. Attiva **Modalita' sviluppatore**.
6. In Chrome/Edge seleziona **Carica estensione non pacchettizzata**. In Firefox seleziona **Carica componente aggiuntivo temporaneo** e scegli `manifest.json`.
   Se Firefox apre una cartella diversa, esegui `INSTALLA_FIREFOX.bat`: evidenzia automaticamente il file corretto e apre la pagina di Firefox.
7. Scegli questa cartella:

```text
UniversalVideoTranslator\_internal\browser_extension
```

8. Fissa **Start UVT AI Overlay** nella barra del browser.

Quando premi **Collega browser**, UVT registra anche l'host Native Messaging per
Firefox in `%APPDATA%\\Mozilla\\NativeMessagingHosts`. Se sposti la build
portatile, ripeti il collegamento.

Comportamento previsto in v0.2.1:

- il click non legge l'URL della pagina;
- il click non compila **Video e file**;
- il click non avvia yt-dlp e non scarica il video;
- il click seleziona **AI Overlay OS**, attende VB-Cable e avvia la traduzione live;
- il popup mostra connessione, sessione e latenza reali e permette di scegliere il profilo e inviare avvia, porta in primo piano e stop;
- durante una sessione, chiudere la finestra principale lascia UVT attivo in background; **Esci completamente da UVT** nel popup arresta e chiude il processo;
- l'icona UVT nell'area di notifica offre **Apri**, **Stop AI Overlay** ed **Esci completamente**;
- aggiornamenti portatili scaricati automaticamente dalle release ufficiali, verificati con SHA-256 e applicati alla chiusura;
- l'estensione si ricarica automaticamente quando rileva una nuova versione dell'app;
- tasti globali: `Ctrl+Alt+F8` avvia/ferma, `Ctrl+Alt+F9` ferma, `Ctrl+Alt+F10` mostra/nasconde l'overlay, `Ctrl+Alt+Su/Giù` regola il volume;
- glossario JSON locale per nomi, marchi e termini tecnici; si apre da **Impostazioni avanzate** e viene ricaricato senza riavvio;
- modalità **Documenti** per TXT, Markdown, HTML, EPUB, DOCX e PDF testuali, con avanzamento, annullamento ed esportazione nello stesso formato;
- **Avvia** mantiene selezionato il video e lascia UVT in background; solo **Apri UVT** porta avanti la finestra desktop;
- se UVT e' gia' aperto, la richiesta viene inoltrata alla finestra esistente.

Se dopo un aggiornamento il click inserisce ancora un link in **Video e file**, rimuovi la vecchia estensione, ricarica quella inclusa nella build corrente e premi di nuovo **Collega browser**.

## Sicurezza E Privacy

UVT e' progettato per uso locale.

- L'estensione usa `storage` e l'accesso limitato a `http://127.0.0.1:17321/*` per comunicare esclusivamente con UVT sul PC.
- L'estensione legge solo i sottotitoli visibili di YouTube/Rumble durante un Overlay attivo; non accede a cookie, cronologia o contenuto generale della scheda.
- Il protocollo `uvt://` trasporta comando, browser, profilo opzionale, timestamp e ID casuale monouso.
- Le richieste duplicate, vecchie o gia' usate vengono ignorate.
- I marker anti-replay non contengono URL e vengono puliti al successivo utilizzo.
- I log non registrano URL, trascrizioni, traduzioni, cookie o nomi dei dispositivi.
- Le connessioni esterne servono solo per download video, dipendenze e modelli scelti dall'utente.

`uvt://` resta un'integrazione locale di Windows, non un canale crittograficamente autenticato end-to-end. Conferma l'apertura del protocollo solo da browser e applicazioni attendibili.

## Dati Locali

UVT salva dati operativi in:

```text
%LOCALAPPDATA%\UniversalVideoTranslator
```

Contenuti principali:

- `settings.json`: preferenze utente.
- `cache\translations-v5.json`: cache traduzioni.
- `logs\uvt.log`: diagnostica rotante privacy-safe.
- `browser-requests\`: marker anti-replay.
- stato routing audio: lease per recupero dopo crash o chiusura forzata.

Per azzerare le preferenze chiudi UVT e rinomina `settings.json`. Per svuotare solo la cache elimina `cache\translations-v5.json`.

## Verifica

```powershell
.\VERIFICA_WINDOWS.bat
```

La verifica e' non mutante e controlla sintassi, test, versioni, dipendenze Python, FFmpeg/ffprobe/ffplay, Deno, SoundVolumeView, eSpeak NG, Kokoro, Faster-Whisper, SoundCard, Ollama, modello predefinito e VB-Cable.

I gate di sviluppo includono inoltre copertura Python con soglia minima del
60%, test del popup in Node.js e controlli statici di accessibilita' e contrasto.

Dall'app puoi rilanciare il controllo essenziale con **Impostazioni → Verifica configurazione**. Per verificare costruzione della GUI reale, pannello contestuale e shutdown:

```powershell
.\.venv\Scripts\python.exe scripts\windows\smoke_gui.py
```

Per misurare in modo ripetibile accuratezza Whisper, fedelta' della traduzione,
tempo Ollama e velocita' Kokoro sui motori locali reali:

```powershell
.\.venv\Scripts\python.exe scripts\windows\benchmark_local.py --output WINDOWS_BENCHMARK.json
```

Il benchmark controllato non sostituisce la misura live: la latenza browser
comprende anche cattura, VAD, pause del parlato e code audio.

Ultima validazione locale registrata in `WINDOWS_VALIDATION.md`:

- Suite pytest completa superata nell'ultima validazione locale.
- Build PyInstaller completata.
- Smoke test single-instance completato.
- ZIP e payload verificati con checksum.

## Build E Release Windows

```powershell
.\BUILD_EXE_WINDOWS.bat
```

Il comando standard crea una release ufficiale solo da un worktree pulito e taggato `v0.2.1`. Per un pacchetto locale di collaudo da modifiche non ancora committate usa esplicitamente:

```powershell
.\BUILD_EXE_WINDOWS.bat -AllowDirty
```

Output principali:

```text
dist-browser-v0.2-release\UniversalVideoTranslator\UniversalVideoTranslator.exe
release\UniversalVideoTranslator-0.2.1-windows-x86_64.zip
release\UniversalVideoTranslator-0.2.1-windows-x86_64.zip.sha256
release\UniversalVideoTranslator-Extension-0.2.1.zip
release\UniversalVideoTranslator-Extension-0.2.1.zip.sha256
```

Distribuisci lo ZIP desktop completo, non il solo EXE. Il pacchetto include
README, changelog, licenza, note terze parti, provenienza e `SHA256SUMS.txt`.
Lo ZIP dell'estensione e' un artefatto separato, deterministico e verificato
contro tutti i file dichiarati dal manifest.

Per creare anche un installer per utente Windows, dopo la build portatile
installa Inno Setup 6 ed esegui:

```powershell
scripts\windows\Build-Installer.ps1
```

Lo script genera `release\UniversalVideoTranslator-0.2.1-windows-x86_64-setup.exe`
e il relativo checksum. La firma Authenticode richiede esplicitamente `-Sign`
e `-CertificateThumbprint`; nessuna identita' di firma viene simulata.

## Componenti Terze Parti

La distribuzione include o usa componenti esterni, documentati in `THIRD_PARTY_NOTICES.md`.

- SoundVolumeView 2.53 e' incluso intatto per il routing audio per-app.
- FFmpeg full build viene copiato nella build Windows.
- Ollama, Deno, VB-Cable e i modelli restano componenti esterni/locali; la libreria Argos è inclusa ma i suoi pacchetti linguistici sono scaricati su richiesta.

Verifica le condizioni di licenza prima di ridistribuire il pacchetto in contesti commerciali.

## Risoluzione Problemi

- **Il click apre Video e file**: estensione vecchia; rimuovila e carica quella da `_internal\browser_extension`.
- **UVT non parte dal browser**: premi **Collega browser** per aggiornare il percorso `uvt://`.
- **VB-Cable non rilevato**: verifica che `CABLE Output (VB-Audio Virtual Cable)` sia tra i dispositivi di registrazione Windows.
- **Firefox si installa ma non si sente l'audio**: l'estensione non cattura direttamente il suono; UVT usa `CABLE Output`. Chiudi e riapri UVT, seleziona quel dispositivo nelle Impostazioni e poi riavvia l'Overlay.
- **Il browser resta su CABLE Input dopo un crash**: riavvia UVT; il lease di routing tenta il ripristino automatico.
- **YouTube fallisce**: controlla Deno, FFmpeg e cookie browser nelle impostazioni avanzate.
- **Serve diagnosi**: consulta `%LOCALAPPDATA%\UniversalVideoTranslator\logs\uvt.log`.

## Limiti Noti

- La qualita' della traduzione dipende dal modello Ollama selezionato.
- Il primo avvio di Kokoro puo' richiedere il download del modello.
- YouTube puo' cambiare controlli di accesso o richiedere cookie validi.
- Il routing audio e' per processo browser, non per singola scheda.
- L'installer opzionale e' per utente Windows e non e' un pacchetto MSI.
- Dopo aver spostato la cartella portatile devi premere di nuovo **Collega browser**.

## Licenza

Il progetto e' distribuito con licenza [Apache 2.0](LICENSE).

## Autore

Sviluppato da [dal1312](https://github.com/dal1312).
