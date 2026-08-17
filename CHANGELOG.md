# Changelog

[Italiano](CHANGELOG.md) | [English](CHANGELOG.en.md)

## Non rilasciato

- Live può ricevere le didascalie visibili di YouTube/Rumble tramite Firefox,
  Chrome o Edge e usarle come testo prioritario rispetto alla trascrizione
  audio; il browser chiamante viene inoltre selezionato automaticamente per
  routing e cookie.
- Nuovo layout desktop responsivo verificato a 1024x700, con stato media vuoto
  esplicito, shutdown pulito e inizializzazione dei motori non invasiva.
- Popup browser ridisegnato con tema chiaro/scuro, focus da tastiera, stato busy,
  messaggi accessibili e test automatici DOM, contrasto e manifest.
- Manifest multipiattaforma compatibile con Chrome/Edge e Firefox 121+, icone
  UVT deterministiche e ZIP estensione separato con checksum SHA-256.
- Gate locale di copertura Python fissato al 60% e integrato nella CI Windows.
- Installer opzionale Inno Setup per utente Windows, bilingue, con checksum e
  firma Authenticode esplicita quando viene fornito un certificato reale.
- Supporto Firefox completo per estensione temporanea e Native Messaging;
  `Collega browser` registra il manifest in `%APPDATA%\\Mozilla\\NativeMessagingHosts`.
- Profilo Live Rapido con selezione automatica di un modello Ollama piccolo già
  installato quando il modello media scelto è grande, per ridurre ritardo e
  segmenti vocali scartati senza cambiare la qualità dei media.
- Installer opzionale `-Kokoro` per ambienti sorgente, con download del modello
  Kokoro-82M al primo utilizzo.
- Rimosse dall'interfaccia e dal runtime le voci Piper e Windows SAPI: restano
  disponibili solo Sara e Nicola di Kokoro; le vecchie impostazioni vengono
  migrate automaticamente.
- Baseline Windows riproducibile con Python 3.10.20, suite completa e preflight
  superati.
- Composizione del percorso Live estratta dalla GUI in un modulo testabile e
  build PyInstaller locale verificata con host browser, estensione, eSpeak NG e
  SoundVolumeView inclusi.
- Supporto opzionale a più interlocutori nei media: diarizzazione, selezione
  della traccia audio e una voce TTS configurabile per i primi due speaker.
- Traduzione offline gratuita con Argos Translate come motore selezionabile e fallback automatico quando Ollama non risponde.
- Voci italiane Piper Paola e Riccardo tramite runtime GPL esterno e installer opzionale con accettazione esplicita delle licenze.
- Installazione Windows robusta quando più versioni Python sono presenti e launcher sorgente con rilevamento Ollama ed exit code affidabile.
- Benchmark locale ripetibile per accuratezza Whisper, fedelta' multilingue, latenza Ollama e velocita' Kokoro; warm-up Ollama completo per eliminare il ritardo della prima traduzione Live.
- Export audio/video separato dalla finestra in un controller dedicato e worker del player progressivo registrati nel supervisore runtime per uno shutdown deterministico.
- Lifecycle della traduzione documenti estratto dalla GUI in un controller dedicato con cancellazione e stato di sessione centralizzati.
- Layout Tk estratto in un modulo dedicato, preflight rilanciabile e warm-up parallelo di Ollama, Whisper e sintesi vocale per ridurre la prima risposta Live.
- Smoke test Windows end-to-end per costruzione GUI, pannello contestuale e shutdown completo.
- Errori operativi centralizzati in messaggi azionabili che indicano problema e correzione senza esporre dettagli interni.
- Visual system estratto dalla finestra principale e selezione automatica di un modello Ollama installato quando quello salvato non è disponibile.
- Pannello impostazioni contestuale, chiuso all'avvio, con rilevamento automatico dei componenti e stato esplicito quando Kokoro non è disponibile.
- Supervisore runtime centralizzato per worker e arresto coordinato delle risorse multimediali.
- Interfaccia desktop ridisegnata come control room locale, con gerarchia tipografica, navigazione dei flussi e stati operativi più chiari.
- Layout adattivo con riposizionamento sicuro sul monitor e pannello Live compattato per mantenere sempre visibile l'output.
- Ponte locale autenticato tra popup e applicazione con stato, profilo e latenza in tempo reale.
- Fallback `uvt://` utilizzato soltanto quando UVT non è ancora in esecuzione.
- Protezione anti-ritardo che scarta i segmenti audio ormai obsoleti.
- Sincronizzazione adattiva che accelera gradualmente la voce tradotta in base a coda e durata del parlato.
- Modalità background con controlli nel popup e nell'area di notifica di Windows.
- Aggiornamenti automatici verificati tramite SHA-256 e sincronizzazione della versione dell'estensione.
- Tasti rapidi globali per sessione, overlay e volume di sistema.
- Glossario locale con equivalenze obbligatorie, ricaricamento automatico e cache separata per ogni revisione.
- Nuova modalità Documenti locale per TXT, Markdown, HTML, EPUB, DOCX e PDF con testo incorporato.
- Arresto completo ripristina routing audio, thread e risorse locali.

## 0.2.1 - 2026-07-31

- La scheda sorgente non viene più sostituita dal protocollo `uvt://`.
- Il click sull'estensione apre e avvia direttamente **AI Overlay OS**; l'URL non viene letto, trasmesso, compilato o scaricato.
- Le richieste browser sono monouso; duplicati, ripristini e richieste non recenti vengono ignorati senza aprire UVT.
- Il consenso iniziale al protocollo viene mostrato in una scheda attiva.
- I link pubblici non tentano più di leggere automaticamente il database cookie del browser; i cookie restano selezionabili manualmente e un errore di accesso attiva il retry senza cookie.
- Il routing audio segue Chrome, Edge o Firefox che ha avviato l'Overlay.
- L'estensione non conserva ID di schede da chiudere dopo un riavvio.
- L'avvio automatico viene annullato se VB-Cable o il routing browser non sono disponibili; ogni errore di setup ripristina l'uscita audio.
- Una singola istanza desktop riceve tramite IPC locale autenticato i click successivi dell'estensione.
- Il routing audio usa un lease persistente e viene recuperato automaticamente dopo crash o chiusura forzata.
- Impostazioni, cache, log rotanti e stato applicativo sono ora centralizzati in `%LOCALAPPDATA%\UniversalVideoTranslator`.
- I log diagnostici escludono URL, cookie, trascrizioni, traduzioni e nomi dei dispositivi.
- Installazione e verifica Windows sono fail-fast e controllano l'intera catena Python, FFmpeg, Deno, Ollama, modello e VB-Cable.
- La build genera una release portatile con licenze, provenienza, hash per file, ZIP deterministico e checksum esterno.

## 0.2.0 - 2026-07-30

- Estensione opzionale Chrome/Edge Manifest V3 con il solo permesso `activeTab`.
- Protocollo locale `uvt://` registrato in HKCU senza privilegi amministrativi.
- Validazione rigorosa: sono accettati soltanto URL HTTP/HTTPS singoli.
- Il click sull'estensione avvia automaticamente download, traduzione e player video con la sola voce italiana.
- Pulsante **Collega browser** e cartella dell'estensione incluse nella build Windows.
- Test di regressione per parsing, registro Windows e avvio GUI.

## 0.1.0 - 2026-07-28

- GUI desktop Windows con tema scuro e menu contestuale.
- Traduzione locale tramite Ollama e selezione del modello dalla GUI.
- Parser SRT/VTT, rilevamento della lingua e cache persistente.
- Pulizia dei sottotitoli YouTube progressivi per eliminare ripetizioni ed eco.
- Trascrizione video/audio con FFmpeg e Faster-Whisper.
- Supporto URL YouTube tramite yt-dlp, cookie del browser e sottotitoli nativi.
- Sintesi vocale Kokoro con Sara e Nicola, senza sostituzione silenziosa con la voce Windows.
- Riproduzione progressiva con buffer iniziale e player ridimensionabile.
- Coda vocale serializzata per impedire la sovrapposizione delle battute.
- Overlay trascinabile sempre in primo piano.
- Esportazione audio WAV/MP3.
- Creazione MP4 con traccia audio italiana.
- Traduzione live dell'audio di sistema Windows.
- Script Windows per installazione completa, verifica e build EXE portatile.
## Local validation build - 2026-08-17

- Generated a local Windows executable build with PyInstaller.
- Validated the source with 37 automated tests.
- Documented the local launch path for `dist-local-20260817`.
- Kept the official project version at `0.2.1`; this build is not published.
