# Universal Video Translator

Applicazione desktop locale per tradurre in italiano i sottotitoli di un video e riprodurli come voce sintetizzata, sincronizzata con le battute originali.

> Stato del progetto: prototipo iniziale. La prima versione lavora con file di sottotitoli `.srt` e `.vtt`; l'acquisizione automatica dell'audio, la trascrizione con Whisper e il doppiaggio completo saranno aggiunti nelle fasi successive.

## Obiettivo

Universal Video Translator nasce per rendere comprensibili in italiano video YouTube, contenuti riprodotti nel browser e file video locali, mantenendo l'elaborazione sul proprio computer quando possibile.

La pipeline prevista è:

1. acquisizione dei sottotitoli o trascrizione dell'audio;
2. traduzione naturale in italiano;
3. generazione della voce italiana;
4. riproduzione sincronizzata con il video;
5. opzionale creazione di una nuova traccia audio.

## Funzioni disponibili nel prototipo

- caricamento di sottotitoli `.srt` e `.vtt`;
- traduzione in italiano tramite Ollama;
- modello locale configurabile, con `qwen3:4b` come valore iniziale;
- sintesi vocale tramite le voci installate in Windows;
- sincronizzazione della lettura con i timestamp dei sottotitoli;
- comandi Avvia, Pausa e Stop;
- scelta della lingua sorgente oppure rilevamento automatico;
- possibilità di nascondere il testo tradotto;
- regolazione della velocità della voce;
- cache locale delle traduzioni.

## Architettura prevista

```text
Video / Browser / File
        |
        v
Sottotitoli esistenti oppure Whisper
        |
        v
Traduzione locale con Ollama
        |
        v
Sintesi vocale italiana
        |
        v
Riproduzione sincronizzata / traccia audio
```

## Requisiti iniziali

- Windows 10 o 11;
- Python 3.11 o superiore;
- [Ollama](https://ollama.com/);
- una voce italiana installata nel sistema.

Installazione rapida su Windows:

```powershell
INSTALL_WINDOWS.bat
AVVIA_WINDOWS.bat
```

Per tradurre direttamente video o audio servono anche FFmpeg e il gruppo dipendenze `audio`.

Installazione manuale:

```powershell
pip install requests pyttsx3
```

Preparazione di Ollama:

```powershell
ollama pull qwen3:4b
ollama serve
```

## Avvio del prototipo

Installazione e avvio dell'interfaccia grafica:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[all]"
python universal_video_translator.py
```

Avvio alternativo da terminale:

```powershell
uvt-cli sottotitoli.srt --show-text
```

Se Ollama è già in esecuzione come servizio, non è necessario avviare manualmente `ollama serve`.

## Configurazione predefinita

```text
Ollama API: http://127.0.0.1:11434/api/chat
Modello:    qwen3:4b
Output:     italiano
```

Questi valori saranno resi configurabili dall'interfaccia e da un file di configurazione.

## Roadmap

### Fase 1 — Prototipo locale

- [x] lettura SRT/VTT;
- [x] traduzione tramite Ollama;
- [x] sintesi vocale Windows;
- [x] sincronizzazione di base;
- [x] struttura modulare del progetto;
- [x] interfaccia grafica Windows;
- [x] test automatici iniziali;
- [x] gestione robusta degli errori.

### Fase 2 — Trascrizione e audio

- [x] estrazione audio con FFmpeg;
- [x] trascrizione locale con Whisper;
- [x] rilevamento automatico della lingua;
- [x] segmentazione con VAD e sincronizzazione di base;
- [ ] voci italiane locali di qualità superiore.

### Fase 3 — Uso universale

- [x] overlay desktop indipendente dal browser;
- [ ] cattura dell'audio di sistema;
- [x] URL YouTube tramite yt-dlp e player locali;
- [x] esportazione WAV/MP3 della traccia audio italiana;
- [ ] pacchetto installabile per Windows.

## Privacy

L'obiettivo principale è consentire una modalità locale: video, sottotitoli, traduzioni e audio possono restare sul PC dell'utente. Eventuali provider cloud saranno opzionali e separati dalla pipeline locale.

## Limiti attuali

- non traduce ancora direttamente l'audio del video;
- richiede sottotitoli SRT/VTT già disponibili;
- la qualità della voce dipende dalle voci installate in Windows;
- la sincronizzazione è ancora sperimentale;
- installer grafico `.exe` non ancora disponibile; sono inclusi gli script Windows.

## Licenza

La licenza del progetto non è ancora stata definita. Prima della distribuzione pubblica verrà aggiunto un file `LICENSE`.

## Autore

Progetto sviluppato da [dal1312](https://github.com/dal1312).
