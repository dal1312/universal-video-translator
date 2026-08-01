# Changelog

[Italiano](CHANGELOG.md) | [English](CHANGELOG.en.md)

## Non rilasciato

- Visual system estratto dalla finestra principale e selezione automatica di un modello Ollama installato quando quello salvato non è disponibile.
- Pannello impostazioni contestuale, chiuso all'avvio, con rilevamento automatico dei componenti e fallback alla voce Windows quando Kokoro non è disponibile.
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
- Sintesi vocale Kokoro con Sara e Nicola, più fallback alle voci Windows.
- Riproduzione progressiva con buffer iniziale e player ridimensionabile.
- Coda vocale serializzata per impedire la sovrapposizione delle battute.
- Overlay trascinabile sempre in primo piano.
- Esportazione audio WAV/MP3.
- Creazione MP4 con traccia audio italiana.
- Traduzione live dell'audio di sistema Windows.
- Script Windows per installazione completa, verifica e build EXE portatile.
