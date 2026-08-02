---
name: revisione-completa-repository
description: Analizza un repository esistente e produce un piano di miglioramento prioritizzato.
user-invocable: true
---

# Revisione completa del repository

## Obiettivo
Analizzare il codice esistente senza modificarlo automaticamente.

## Procedura
1. Comprendi struttura, tecnologie e dipendenze.
2. Verifica build, test e avvio quando possibile.
3. Analizza:
   - architettura
   - qualità del codice
   - sicurezza
   - prestazioni
   - documentazione
   - CI/CD
4. Classifica ogni problema come:
   - P0 Bloccante
   - P1 Critico
   - P2 Alto
   - P3 Medio
   - P4 Basso

## Per ogni problema indica
- File
- Funzione/classe
- Evidenza
- Impatto
- Correzione consigliata
- Test da aggiungere

## Rapporto finale
1. Sintesi esecutiva
2. Mappa del repository
3. Stato di build e test
4. Problemi trovati
5. Punti di forza
6. Piano di miglioramento
7. Ticket consigliati
8. Ordine di esecuzione
9. Componenti da non modificare
10. Verdetto finale

Non modificare il codice finché il piano non viene approvato.
