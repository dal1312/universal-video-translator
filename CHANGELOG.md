# Changelog

[Italiano](CHANGELOG.md) | [English](CHANGELOG.en.md)

## 0.2.1 - 2026-07-31

- La scheda sorgente non viene più sostituita dal protocollo `uvt://`.
- Il click sull'estensione apre e avvia direttamente **AI Overlay OS**; l'URL non viene letto, trasmesso, compilato o scaricato.
- Le richieste browser sono monouso; duplicati, ripristini e richieste non recenti vengono ignorati senza aprire UVT.
- Il consenso iniziale al protocollo viene mostrato in una scheda attiva.
- I link pubblici non tentano più di leggere automaticamente il database cookie del browser; i cookie restano selezionabili manualmente e un errore di accesso attiva il retry senza cookie.
- Il routing audio segue Chrome, Edge o Firefox che ha avviato l'Overlay.
- L'estensione non richiede alcun permesso browser e non conserva ID di schede da chiudere dopo un riavvio.
- L'avvio automatico viene annullato se VB-Cable o il routing browser non sono disponibili; ogni errore di setup ripristina l'uscita audio.

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
