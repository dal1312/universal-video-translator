# Revisione completa del repository

Data della revisione: 2026-08-02
Repository analizzato: `universal-video-translator-browser-v0.2`
Ambito: sola cartella locale; nessun accesso a GitHub; nessuna modifica al codice applicativo.

## 1. Sintesi esecutiva

Universal Video Translator è un'applicazione desktop Windows articolata e già
funzionale, con traduzione locale, trascrizione, sintesi vocale, elaborazione di
media e documenti, integrazione browser, routing audio, aggiornamento portatile
e packaging PyInstaller. La base tecnica è superiore a un prototipo: sono
presenti separazione parziale in controller e servizi, persistenza atomica,
code limitate, gestione dello shutdown, controlli anti-replay, test automatici,
preflight Windows e provenienza della release.

Il worktree corrente non è però qualificabile per una release. La suite locale
ha prodotto **195 test superati e 1 fallito**, mentre il documento di validazione
continua a dichiarare uno stato PASS riferito a un commit precedente. Inoltre
sono presenti modifiche locali non committate proprio nei componenti più
sensibili: cattura Live, discovery dei runtime, trascrizione e player media.

I due rischi progettuali più importanti sono:

1. il bridge HTTP locale accetta un'intestazione statica e qualsiasi origine di
   estensione browser, consentendo comandi come `quit` senza un segreto di
   sessione;
2. l'aggiornamento automatico verifica un hash scaricato dalla stessa release
   dell'archivio, ma non una firma con una radice di fiducia indipendente.

**Verdetto:** buona base per un prodotto locale personale, ma il branch corrente
richiede un ciclo di stabilizzazione e hardening prima di essere considerato
distribuibile. Priorità immediata: ripristinare la suite verde, congelare un
baseline riproducibile e proteggere bridge e updater.

## 2. Metodo e perimetro

Sono stati esaminati esclusivamente file locali:

- sorgenti Python in `src/uvt`;
- estensione Manifest V3 in `browser_extension`;
- test in `tests`;
- configurazione Python e PyInstaller;
- script Windows di installazione, verifica, benchmark e release;
- documentazione, benchmark e rapporto di validazione;
- stato Git e statistiche del worktree locale.

Verifiche eseguite:

```text
ruff check src tests scripts     PASS
pytest -q                        FAIL: 1 failed, 195 passed
pip check                        PASS
```

Non sono stati eseguiti download, build di release, pubblicazioni o interrogazioni
di GitHub. L'unico file creato dalla revisione è questo rapporto.

## 3. Mappa del repository

| Area | Responsabilità | Valutazione |
|---|---|---|
| `src/uvt/gui.py` | orchestrazione Tk, eventi, sessioni e servizi | funzionale ma monolitica, 1.595 righe |
| `src/uvt/ui_layout.py`, `ui_theme.py` | layout e visual system | separazione utile, ancora fortemente accoppiata alla finestra |
| `workflow.py`, `controllers.py`, `session.py` | casi d'uso e stato operativo | direzione architetturale corretta |
| `live.py`, `vad.py`, `adaptive_sync.py`, `latency.py` | pipeline audio Live | completa ma concorrente e sensibile ai runtime Windows |
| `transcription.py`, `ollama.py`, `translation.py`, `tts.py` | motori AI locali | buona astrazione iniziale, discovery e fallback ancora fragili |
| `player.py`, `progressive.py`, `media_player.py`, `export.py` | playback ed esportazione | responsabilità distribuite, forte dipendenza da FFmpeg/FFplay |
| `documents.py` | TXT/Markdown/HTML/EPUB/DOCX/PDF | funzione ampia con test dedicati |
| `browser_bridge.py`, `browser_protocol.py`, `instance_ipc.py` | estensione, protocollo e single-instance | IPC interno robusto; bridge HTTP da irrobustire |
| `audio_routing.py`, `hotkeys.py`, `tray.py` | integrazione Windows | ben circoscritta ma difficilmente portabile |
| `updates.py` | aggiornamento portatile | controlli di percorso buoni, trust model insufficiente |
| `scripts/windows` | installazione, preflight, benchmark e release | copertura operativa ampia |
| `tests` | 34 moduli, circa 3.742 righe | buona ampiezza; copertura non misurata |

Dimensioni indicative:

- circa **9.477 righe** di sorgente Python;
- **34 file di test**;
- **118 file tracciati**;
- `gui.py` rappresenta da sola circa il 17% del sorgente Python.

## 4. Stato di build, test e worktree

### Stato corrente

- Branch locale: `feature/browser-integration-v0.2`.
- Ultimo commit locale osservato: `6c995f6`.
- Modifiche non committate in:
  `AVVIA_WINDOWS.bat`, `live.py`, `media_player.py`, `ollama.py`,
  `readiness.py`, `transcription.py`.
- File non tracciati: `SKILL.md` e `assets/models/`.
- Lint Ruff: PASS.
- Integrità dipendenze installate: PASS.
- Test: **FAIL, 1 su 196**.

### Test fallito

`tests/test_live.py::test_capture_creates_wasapi_device_in_com_thread`

Il fake module `soundcard` usato dal test non espone
`SoundcardRuntimeWarning`; l'accesso diretto in `live.py` interrompe `_capture`
prima che il percorso COM venga completato. In produzione la classe esiste, ma
il fallimento dimostra che la nuova gestione degli avvisi ha ampliato il
contratto implicito della dipendenza e ha rotto il gate di regressione.

### Build e validazione pregresse

`WINDOWS_VALIDATION.md` registra una build PASS con 187 test e commit
`226c5f9`, mentre il worktree corrente contiene 196 test e modifiche successive.
Quel documento resta utile come evidenza storica, ma **non certifica il codice
corrente**. Non è stata eseguita una nuova build durante questa revisione.

### Igiene del repository

La radice contiene molte directory `.pytest-tmp-*` e `.test-cache-*`, oltre a
build e artefatti di release. Sono in gran parte ignorate da Git, ma rendono
l'ambiente rumoroso e aumentano il rischio di analizzare o distribuire output
stale. Il database Git condiviso dal worktree segnala inoltre circa **2,33 GiB
di oggetti garbage**; la manutenzione va effettuata sul repository principale,
non automaticamente da questo worktree.

## 5. Problemi trovati

### P0 — Gate di test rosso nel worktree corrente

- **File:** `src/uvt/live.py`, `tests/test_live.py`
- **Funzione/classe:** `LiveTranslator._capture`
- **Evidenza:** `pytest -q` termina con 1 fallimento e 195 successi; il fake
  `soundcard` non contiene `SoundcardRuntimeWarning`.
- **Impatto:** nessuna release affidabile; CI fallirebbe sul codice corrente;
  rischio che la gestione degli avvisi mascheri o interrompa inizializzazioni
  parziali.
- **Correzione consigliata:** risolvere la categoria warning con `getattr`,
  importarla dal modulo concreto con fallback oppure confinare il filtro in un
  adapter SoundCard; mantenere sempre il `finally` COM verificabile.
- **Test da aggiungere:** modulo SoundCard minimo senza classe warning; modulo
  reale con warning; eccezione prima e dopo `CoInitializeEx`; verifica esatta di
  `CoUninitialize`.

### P1 — Bridge browser locale autenticato solo nominalmente

- **File:** `src/uvt/browser_bridge.py`
- **Funzione/classe:** `Handler._authorized`, `LocalBrowserBridge._origin_allowed`
- **Evidenza:** senza header `Origin` basta inviare
  `X-UVT-Client: uvt-extension-v1`; con `Origin` viene accettata qualsiasi
  origine che inizi con `chrome-extension://` o `moz-extension://`.
- **Impatto:** qualunque processo locale o estensione installata può interrogare
  lo stato e inviare `overlay`, `stop`, `focus` o `quit`. Il bind loopback limita
  l'esposizione, ma non costituisce autenticazione.
- **Correzione consigliata:** token casuale per installazione/sessione, handshake
  tramite protocollo o native messaging, allowlist dell'ID dell'estensione e
  confronto costante; separare i permessi di lettura da quelli di comando.
- **Test da aggiungere:** richiesta senza token, token errato, origine di altra
  estensione, replay, rotazione token, comando `quit` non autorizzato.

### P1 — Auto-update verificato con checksum non indipendente

- **File:** `src/uvt/updates.py`
- **Funzione/classe:** `AutomaticUpdater.check_and_stage`,
  `launch_pending_update`
- **Evidenza:** archivio e `.sha256` provengono dagli asset della stessa release;
  successivamente viene eseguito uno script PowerShell con
  `ExecutionPolicy Bypass` che sovrascrive la directory applicativa.
- **Impatto:** la compromissione dell'account o della release permette di
  sostituire sia archivio sia checksum. SHA-256 garantisce integrità di
  trasporto, non autenticità dell'editore.
- **Correzione consigliata:** firma Ed25519/minisign con chiave pubblica
  incorporata oppure Authenticode obbligatorio e verificato prima dello staging;
  rendere atomico il cambio versione e prevedere rollback.
- **Test da aggiungere:** firma assente/errata, certificato inatteso, archivio
  valido con payload alterato, interruzione durante copia, rollback dopo avvio
  fallito.

### P1 — Evidenza di release non allineata al codice

- **File:** `WINDOWS_VALIDATION.md`, `WINDOWS_BENCHMARK.json`, changelog
- **Funzione/classe:** processo di qualificazione release
- **Evidenza:** rapporto PASS su commit `226c5f9` e 187 test; HEAD osservato
  `6c995f6`, 196 test, worktree sporco e suite fallita.
- **Impatto:** possibile distribuzione di binari o dichiarazioni riferiti a un
  codice differente; diagnosi e rollback poco affidabili.
- **Correzione consigliata:** generare la validazione solo da tag pulito, inserire
  commit e hash artefatto in un report immutabile, rifiutare `dirty: true` per
  qualunque artefatto denominato release.
- **Test da aggiungere:** release gate che confronta HEAD, tag, versione,
  provenance, checksum e risultato test nello stesso job.

### P2 — CI installa solo dipendenze `dev`

- **File:** `.github/workflows/ci.yml`, `pyproject.toml`
- **Funzione/classe:** job `test`
- **Evidenza:** CI usa `pip install -e ".[dev]"`; non installa gruppi `audio`,
  `live`, `kokoro`, `translation` o `all`. Controlla inoltre solo
  `service-worker.js`, non `popup.js`.
- **Impatto:** import e incompatibilità delle dipendenze principali possono
  arrivare fino al PC Windows o alla fase di packaging.
- **Correzione consigliata:** matrice minima/core e Windows/full vincolata al
  constraints file; test di import; syntax check di tutti i JavaScript; job
  periodico di build PyInstaller e smoke test.
- **Test da aggiungere:** installazione pulita Python 3.10, import di tutti i
  motori, package smoke, avvio GUI headless/Windows, manifest validation.

### P2 — `TranslatorWindow` resta un god object

- **File:** `src/uvt/gui.py`
- **Funzione/classe:** `TranslatorWindow`
- **Evidenza:** circa 1.595 righe; gestisce UI, lifecycle, aggiornamenti,
  bridge, routing, modelli, dispositivi, hotkey, tray e sessioni.
- **Impatto:** elevato costo di modifica, rischio di regressioni incrociate,
  test basati su monkeypatch e ordine di inizializzazione.
- **Correzione consigliata:** estrarre presenter/view-model per Media, Live e
  Documenti; introdurre un composition root; rendere i servizi dipendenze
  esplicite anziché costruirli nella finestra.
- **Test da aggiungere:** test dei presenter senza Tk, test di wiring della sola
  composizione e pochi smoke test GUI end-to-end.

### P2 — Discovery dei runtime duplicata e dipendente dall'installazione

- **File:** `transcription.py`, `media_player.py`, `ollama.py`, `readiness.py`,
  script Windows
- **Funzione/classe:** `find_media_tool`, `ensure_ffmpeg`,
  `ollama_executable`, readiness e launcher
- **Evidenza:** il worktree contiene correzioni locali per percorsi WinGet e
  `%LOCALAPPDATA%`; build, preflight e runtime risolvono gli strumenti con
  strategie differenti.
- **Impatto:** stato GUI incoerente con l'esecuzione reale; errori “non trovato”
  nonostante il componente sia installato; differenze tra sorgente e pacchetto.
- **Correzione consigliata:** unico `RuntimeResolver` con ordine documentato:
  override utente, bundle, PATH, installazioni note; risultato strutturato con
  versione e provenienza, riusato da preflight, GUI e build.
- **Test da aggiungere:** PATH assente, WinGet presente, bundle presente,
  override invalido, più versioni, nomi file con maiuscole e spazi.

### P2 — Compressione vocale può alterare silenziosamente il contenuto

- **File:** `src/uvt/live.py`
- **Funzione/classe:** `compact_speech_text`, `LiveTranslator._speak`
- **Evidenza:** oltre 1,8 secondi di coda il testo viene troncato a un budget di
  parole con ellissi; la traduzione visualizzata può differire da quella letta.
- **Impatto:** perdita di informazioni in dibattiti, tutorial, contenuti legali o
  tecnici; comportamento non selezionabile dall'utente.
- **Correzione consigliata:** opzione esplicita “fedeltà/recupero ritardo”,
  conservazione di soggetto-verbo-oggetto tramite riassunto controllato oppure
  salto dichiarato; mostrare contatore e testo effettivamente pronunciato.
- **Test da aggiungere:** nomi propri, numeri, negazioni, frasi brevi, più frasi,
  coda oscillante e coerenza tra overlay e audio.

### P2 — Privacy “locale” con eccezioni di rete non completamente esplicitate

- **File:** `downloader.py`, `updates.py`, installer motori, README
- **Funzione/classe:** opzioni yt-dlp, updater, download modelli
- **Evidenza:** yt-dlp abilita `remote_components: {ejs:github}`; updater e
  modelli effettuano richieste esterne. L'elaborazione resta locale, ma non tutte
  le modalità sono offline.
- **Impatto:** aspettative privacy errate e funzionamento degradato dietro DNS,
  proxy o filtri aziendali.
- **Correzione consigliata:** matrice chiara “offline / rete al primo uso / rete
  per operazione”; consenso per download remoti; diagnostica endpoint senza
  ripetizioni infinite.
- **Test da aggiungere:** modalità offline forzata, endpoint irraggiungibile,
  timeout, proxy, DNS bloccato e fallback locale.

### P3 — Eccezioni troppo generiche e diagnostica povera

- **File:** soprattutto `gui.py`, `live.py`, `downloader.py`, `progressive.py`
- **Funzione/classe:** numerosi blocchi `except Exception`
- **Evidenza:** il logger salva spesso solo tipo e ultima posizione, non messaggio
  o catena causale; gli errori recenti sono stati distinguibili solo per riga.
- **Impatto:** popup generici, investigazioni lente, possibile assorbimento di
  errori di programmazione come fallback operativo.
- **Correzione consigliata:** eccezioni di dominio, messaggio sanificato,
  `exc_info` nei log locali, event ID e contesto non sensibile; catture generiche
  solo ai confini di thread/UI.
- **Test da aggiungere:** catena causale, redazione di URL/cookie/testo, codici
  errore stabili e messaggi utente specifici.

### P3 — Nessuna misura automatica della coverage

- **File:** `pyproject.toml`, CI
- **Funzione/classe:** configurazione test
- **Evidenza:** 34 moduli di test ma nessun `coverage.py`, branch coverage o
  soglia minima.
- **Impatto:** il numero elevato di test non dimostra copertura delle diramazioni
  concorrenti, degli errori e degli installer.
- **Correzione consigliata:** coverage branch per moduli core, soglia iniziale
  realistica e incremento graduale; esclusione motivata dei binding Windows.
- **Test da aggiungere:** non applicabile; introdurre report XML/HTML e gate.

### P3 — Repository operativo troppo rumoroso

- **File:** radice repository, `.gitignore`
- **Funzione/classe:** gestione artefatti locali
- **Evidenza:** decine di directory temporanee di sessioni precedenti, build e
  release locali molto grandi; object store condiviso con 2,33 GiB di garbage.
- **Impatto:** confusione tra artefatti correnti e stale, scansioni lente, backup
  più pesanti e maggiore rischio di packaging accidentale.
- **Correzione consigliata:** usare un'unica directory `.work/` ignorata, temp in
  `%TEMP%`, comando di pulizia conservativo e manutenzione Git pianificata dal
  repository principale.
- **Test da aggiungere:** packaging deve rifiutare file inattesi e produrre
  manifest deterministico.

### P3 — Vincoli di licenza e distribuzione richiedono un gate dedicato

- **File:** `THIRD_PARTY_NOTICES.md`, `third_party/manifest.json`, spec e release
- **Funzione/classe:** packaging terze parti
- **Evidenza:** applicazione Apache-2.0 distribuita con FFmpeg full GPL e
  SoundVolumeView soggetto a condizioni proprie; Piper è correttamente isolato.
- **Impatto:** redistribuzione commerciale o incompleta potenzialmente non
  conforme; il singolo EXE non è distribuibile da solo.
- **Correzione consigliata:** SBOM, inventario licenze generato, review legale
  prima della pubblicazione, controllo che ZIP contenga sempre fonti/notice
  richiesti dalle specifiche licenze applicabili.
- **Test da aggiungere:** verifica automatica notice, licenze, versioni, hash e
  assenza di componenti GPL non previsti dentro il runtime applicativo.

### P4 — Naming centrato su Ollama non più coerente

- **File:** `workflow.py`, `settings.py`, GUI
- **Funzione/classe:** `RunSettings.ollama_model`, `AppSettings.ollama_model`
- **Evidenza:** il campo contiene anche `argos:offline`.
- **Impatto:** debito semantico e futuri errori quando saranno aggiunti altri
  provider.
- **Correzione consigliata:** migrare a `translation_model` e separare
  `translation_engine`; mantenere compatibilità schema per le impostazioni.
- **Test da aggiungere:** migrazione settings v1→v2 e round-trip dei provider.

## 6. Punti di forza

- Persistenza di cache e impostazioni con file temporaneo, `fsync` e
  sostituzione atomica.
- IPC single-instance con token casuale e confronto HMAC costante.
- Protocollo `uvt://` con UUID, finestra temporale e claim anti-replay.
- Estensione con permessi limitati a storage e loopback; nessun content script.
- Code audio e voce limitate, gestione dello shutdown e routing con lease.
- Protezione ZIP-slip nell'estrazione degli aggiornamenti.
- Release deterministica con checksum per file e provenienza.
- Hash verificati per SoundVolumeView e presenza delle licenze nel packaging.
- Test numerosi sui domini principali, incluso comportamento concorrente e GUI.
- Argos isolato come fallback offline e Piper mantenuto in runtime esterno per
  evitare contaminazione diretta della licenza Apache.
- Documentazione bilingue e script Windows orientati a utenti non sviluppatori.

## 7. Piano di miglioramento

### Fase 0 — Ripristino baseline

1. Correggere il test Live e riportare la suite a 196/196.
2. Separare o committare intenzionalmente le modifiche locali correnti.
3. Eseguire preflight, GUI smoke e test media reali.
4. Rigenerare validazione e benchmark dal medesimo commit pulito.

**Uscita:** worktree pulito, test/lint/preflight verdi, documento di validazione
con HEAD e hash artefatti coerenti.

### Fase 1 — Hardening locale

1. Autenticare realmente il bridge browser.
2. Firmare gli aggiornamenti con chiave indipendente.
3. Centralizzare la discovery dei runtime.
4. Migliorare log ed errori di dominio.

**Uscita:** comandi locali non falsificabili da processi/estensioni arbitrarie,
update verificabile offline, diagnostica riproducibile.

### Fase 2 — Stabilità architetturale

1. Estrarre presenter e composition root da `TranslatorWindow`.
2. Separare provider e modello di traduzione nello schema settings.
3. Rendere configurabile la politica di recupero ritardo.
4. Aggiungere adapter per SoundCard/FFmpeg/Ollama testabili senza monkeypatch
   globale.

**Uscita:** core applicativo testabile senza Tk e senza runtime Windows reali.

### Fase 3 — Qualificazione e manutenzione

1. Espandere CI ai gruppi optional e al packaging Windows.
2. Introdurre branch coverage e SBOM.
3. Consolidare directory temporanee e manutenzione artefatti.
4. Documentare con precisione quando viene usata la rete.

**Uscita:** release riproducibile, tracciabile e manutenibile nel tempo.

## 8. Ticket consigliati

| ID | Priorità | Titolo | Criterio di accettazione |
|---|---:|---|---|
| UVT-001 | P0 | Ripristinare test COM/SoundCard | 196/196 test verdi con fake SoundCard minimo |
| UVT-002 | P1 | Tokenizzare il bridge HTTP | nessun comando senza token valido e origine autorizzata |
| UVT-003 | P1 | Firmare gli aggiornamenti | update rifiutato se firma o publisher non coincidono |
| UVT-004 | P1 | Rigenerare baseline release | HEAD, tag, provenance, test e ZIP riferiti allo stesso commit |
| UVT-005 | P2 | RuntimeResolver unico | GUI, preflight, build e runtime restituiscono gli stessi path |
| UVT-006 | P2 | CI Windows full | installazione clean, optional imports, test, JS e package smoke verdi |
| UVT-007 | P2 | Estrarre presenter GUI | flussi Media/Live/Documenti testabili senza creare `Tk` |
| UVT-008 | P2 | Politica coda vocale | modalità fedeltà/recupero selezionabile e osservabile |
| UVT-009 | P3 | Error taxonomy e logging | ogni errore operativo ha event ID, causa sanificata e rimedio |
| UVT-010 | P3 | Coverage e concorrenza | branch coverage pubblicata e soglia concordata |
| UVT-011 | P3 | SBOM e license gate | inventario componenti/licenze incluso e verificato nella release |
| UVT-012 | P3 | Igiene workspace | temp sotto una directory unica e nessun artefatto stale nel payload |
| UVT-013 | P4 | Migrare naming traduzione | schema provider/modello con migrazione retrocompatibile |

## 9. Ordine di esecuzione

```text
UVT-001
  → UVT-004
  → UVT-002 + UVT-003
  → UVT-005 + UVT-009
  → UVT-006
  → UVT-007 + UVT-008 + UVT-013
  → UVT-010 + UVT-011 + UVT-012
```

Non conviene proseguire con nuove funzionalità prima di UVT-001 e UVT-004:
senza baseline verde non è possibile distinguere una regressione nuova da una
già presente.

## 10. Componenti da non modificare automaticamente

- `assets/models/`: modelli locali dell'utente, non tracciati.
- `third_party/SoundVolumeView/*`: pacchetto vendor da mantenere integro e
  verificato tramite hash.
- `release/`, `dist-*`, `build-*`: artefatti derivati; vanno rigenerati, non
  corretti manualmente.
- `%LOCALAPPDATA%\UniversalVideoTranslator`: impostazioni, cache, log, lease,
  token e modelli dell'utente.
- `.git` del worktree e object store condiviso: nessuna pulizia automatica senza
  backup e verifica del repository principale.
- `LICENSE` e notice terze parti: modifiche solo dopo verifica delle condizioni
  di redistribuzione.
- formati di protocollo, IPC e settings persistenti: richiedono migrazione
  retrocompatibile, non cambi diretti.

## 11. Verdetto finale

Il progetto ha già valore concreto: integra in locale capacità che normalmente
richiedono più applicazioni separate e possiede una quantità significativa di
test e infrastruttura Windows. Non è un esperimento usa-e-getta.

La maturità attuale è però sbilanciata: molte funzionalità, release tooling
ambizioso e documentazione ricca, ma baseline corrente rossa e due confini di
sicurezza non ancora adeguati alle dichiarazioni di “autenticato” e “firmato”.

**Valutazione complessiva: 7/10 come applicazione locale in sviluppo; 5/10 come
prodotto distribuibile nello stato corrente.** Dopo baseline verde, bridge con
token e updater firmato, il progetto può realisticamente raggiungere uno stato
di release candidate solido senza una riscrittura completa.

## 12. Stato delle correzioni applicate

Aggiornamento locale successivo alla revisione:

- UVT-001: corretta la regressione SoundCard/COM; il filtro warning è ora
  compatibile anche con backend SoundCard minimali e non interrompe il `finally`
  che rilascia COM.
- UVT-003: download consentiti solo via HTTPS, limite di 2 GiB e verifica
  Authenticode sia allo staging sia prima dell'applicazione. Il certificato del
  nuovo eseguibile deve coincidere con quello dell'eseguibile installato.
- UVT-005: introdotto un resolver condiviso per PATH, runtime bundled, Ollama e
  tool FFmpeg installati da WinGet.
- UVT-006: CI estesa agli extra completi con constraints, `pip check` e controllo
  sintattico di entrambi gli script dell'estensione.
- Bridge: eliminata l'autorizzazione basata sul solo header statico
  `X-UVT-Client`; le richieste HTTP devono provenire da un'origine extension.
  La tokenizzazione completa resta un intervento separato perché richiede un
  canale sicuro di provisioning del segreto (preferibilmente Native Messaging).

Verifiche eseguite dopo le modifiche:

- Ruff: PASS sull'intero albero `src`, `tests`, `scripts`.
- JavaScript: PASS per `service-worker.js` e `popup.js`.
- Suite completa: 200 PASS con Python 3.10.6, inclusa la regressione
  COM/SoundCard.
- Dipendenze (`pip check`), compilazione Python, Ruff, sintassi JavaScript e
  `git diff --check`: PASS.
