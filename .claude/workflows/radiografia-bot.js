export const meta = {
  name: 'radiografia-bot',
  description: 'Audit profondo del trading bot su 10 dimensioni, ogni problema verificato, report per gravità in consegne/audit/',
  whenToUse: 'Quando Nicola dice "radiografia", "analizza tutto il bot", "trova tutti i bug".',
  phases: [
    { title: 'Audit', detail: 'una dimensione per agente, in sola lettura' },
    { title: 'Verifica', detail: 'ogni problema trovato viene verificato (refutato o confermato)' },
    { title: 'Sintesi', detail: 'report per gravità in consegne/audit/' },
  ],
}

// Le 10 dimensioni della radiografia. Ognuna è in SOLA LETTURA sul codice del bot.
const DIMENSIONI = [
  { key: 'strategia-edge',  agent: 'quant-strategist',
    prompt: 'Audita le strategie in user_data/strategies/ e il motore research/. Cerca: edge senza tesi economica, overfitting (confronta IS vs OOS in results/research/summary.json), parametri troppo tarati, regole fragili. SOLA LETTURA: non modificare nulla.' },
  { key: 'rischio',         agent: 'risk-manager',
    prompt: 'Audita la gestione del rischio: stoploss, custom_stoploss, protections (MaxDrawdown/StoplossGuard/Cooldown), max_open_trades, leva, stoploss_on_exchange. Cerca buchi che possono far perdere capitale. SOLA LETTURA.' },
  { key: 'esecuzione',      agent: 'trader-esecuzione',
    prompt: 'Audita l\'esecuzione: entry_pricing/exit_pricing/order_types/unfilledtimeout nei config, slippage e fee non considerati, rate limit. SOLA LETTURA.' },
  { key: 'dati',            agent: 'data-engineer',
    prompt: 'Audita i dati: qualità di user_data/data_sources/*.csv, gap/duplicati, rischio look-ahead nella pipeline research/data.py e negli indicatori. SOLA LETTURA.' },
  { key: 'ml-overfitting',  agent: 'ml-engineer',
    prompt: 'Audita il ramo ML (research/ml_meta.py, scripts di training): purged walk-forward corretto? look-ahead nelle feature? gate OOS presente? SOLA LETTURA.' },
  { key: 'sicurezza-chiavi',agent: 'security',
    prompt: 'Audita la sicurezza: segreti nei config (user_data/config*.json), credenziali deboli (es. password "solbot123", jwt "CAMBIAMI"), copertura .gitignore di .env/chiavi, withdrawal whitelist. SOLA LETTURA.' },
  { key: 'performance',     agent: 'performance-analytics',
    prompt: 'Audita la misura della performance: i numeri citati (README/docs) sono onesti e riproducibili? c\'è attribuzione PnL? il "+10.000%" era lookahead? SOLA LETTURA.' },
  { key: 'infra',           agent: 'devops-sre',
    prompt: 'Audita l\'infra: docker-compose*.yml, scripts/vps-setup.sh, restart policy, monitoring/alert (Telegram OFF?), gestione log, failover. SOLA LETTURA.' },
  { key: 'test',            agent: 'qa-test',
    prompt: 'Audita la copertura di test: esistono tests/? c\'è una CI? parità paper↔live verificata? casi limite coperti? SOLA LETTURA.' },
  { key: 'errori-conn',     agent: 'exchange-dev',
    prompt: 'Audita connettività e gestione errori: ccxt config, reconnect, idempotenza ordini, gestione timeout/errori API Kraken. SOLA LETTURA.' },
]

const TROVATI = {
  type: 'object',
  properties: {
    dimensione: { type: 'string' },
    problemi: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          titolo: { type: 'string' },
          gravita: { type: 'string', enum: ['bloccante', 'serio', 'minore'] },
          file: { type: 'string' },
          evidenza: { type: 'string' },
          fix_proposto: { type: 'string' },
          colore: { type: 'string', enum: ['verde', 'giallo', 'rosso'] },
        },
        required: ['titolo', 'gravita', 'file', 'evidenza', 'colore'],
      },
    },
  },
  required: ['dimensione', 'problemi'],
}

const VERDETTO = {
  type: 'object',
  properties: {
    confermato: { type: 'boolean' },
    motivo: { type: 'string' },
  },
  required: ['confermato', 'motivo'],
}

// Pipeline: ogni dimensione viene auditata e poi OGNI suo problema viene verificato
// (un secondo senior prova a refutarlo) senza barriera tra le dimensioni.
const risultati = await pipeline(
  DIMENSIONI,
  (d) => agent(d.prompt, { label: `audit:${d.key}`, phase: 'Audit', agentType: d.agent, schema: TROVATI }),
  (trovato, d) => parallel((trovato?.problemi || []).map((p) => () =>
    agent(
      `Verifica adversarialmente questo problema dell'audit "${d.key}". Prova a REFUTARLO leggendo il file indicato. ` +
      `Problema: ${p.titolo}\nFile: ${p.file}\nEvidenza: ${p.evidenza}\n` +
      `Se l'evidenza non regge, confermato=false. Se è reale, confermato=true. SOLA LETTURA.`,
      { label: `verifica:${d.key}`, phase: 'Verifica', schema: VERDETTO }
    ).then((v) => ({ ...p, dimensione: d.key, verdetto: v }))
  ))
)

const confermati = risultati.flat().filter(Boolean).filter((p) => p.verdetto?.confermato)

// Ordina per gravità
const ordine = { bloccante: 0, serio: 1, minore: 2 }
confermati.sort((a, b) => (ordine[a.gravita] ?? 9) - (ordine[b.gravita] ?? 9))

phase('Sintesi')
const report = await agent(
  `Scrivi il report della radiografia del bot in italiano, ordinato per gravità (🔴 bloccanti, 🟠 seri, 🟡 minori). ` +
  `Per ogni problema: titolo, file, evidenza, fix proposto, colore 🟢🟡🔴. ` +
  `In testa: un riassunto esecutivo con i 3 problemi più gravi e le 3 mosse a maggior impatto su profitto/efficienza/robustezza. ` +
  `Salva il file in consegne/audit/ con nome AAAA-MM-GG-radiografia.md (usa la data di oggi). ` +
  `Problemi confermati (JSON):\n${JSON.stringify(confermati, null, 2)}`,
  { label: 'sintesi-report', phase: 'Sintesi' }
)

log(`Radiografia completata: ${confermati.length} problemi confermati.`)
return { problemi_confermati: confermati.length, report }
