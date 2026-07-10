export const meta = {
  name: 'scansione-news',
  description: 'Fan-out multi-fonte di notizie/catalizzatori crypto, dedup, e stima dell\'impatto sul book',
  whenToUse: 'Quando Nicola dice "scansiona news", "cosa è successo?", "ci sono catalizzatori?".',
  phases: [
    { title: 'Raccolta', detail: 'più angoli di lettura sul log news dell\'ora' },
    { title: 'Impatto', detail: 'stima impatto sul book per ogni catalizzatore' },
    { title: 'Sintesi', detail: 'digest dedotto + sentinelle da far scattare' },
  ],
}

// Prima si esegue cervello/news.py per avere il log fresco dell'ora.
// (Lo fa il desk prima di lanciare il workflow, oppure il cron orario.)
// Qui i senior leggono Bot-Vault/90-Memoria-AI/news/ e il web e sintetizzano.

const ANGOLI = [
  { key: 'mercato',   agent: 'news-intelligence',
    prompt: 'Leggi l\'ultimo log in Bot-Vault/90-Memoria-AI/news/ (e se serve il web). Estrai i catalizzatori di MERCATO: listing/delisting, hack/exploit, movimenti grossi, annunci di progetti.' },
  { key: 'macro-reg', agent: 'macro-analyst',
    prompt: 'Estrai i catalizzatori MACRO/REGOLAMENTARI dalle ultime news: Fed/tassi, ETF flow, decisioni regolatorie (SEC/EU/MiCA), DXY. Fonte: Bot-Vault/90-Memoria-AI/news/ + web.' },
  { key: 'onchain',   agent: 'onchain-analyst',
    prompt: 'Estrai segnali ON-CHAIN rilevanti dalle news e dai dati free: flussi exchange, whale, stablecoin, funding/OI estremi. Fonte: Bot-Vault/90-Memoria-AI/news/ + web.' },
  { key: 'sentiment', agent: 'sentiment-analyst',
    prompt: 'Estrai il quadro di SENTIMENT: Fear&Greed (dal log news.py), narrative dominanti, estremi contrarian. Fonte: Bot-Vault/90-Memoria-AI/news/.' },
]

const CATALIZZATORI = {
  type: 'object',
  properties: {
    angolo: { type: 'string' },
    catalizzatori: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          titolo: { type: 'string' },
          fonte: { type: 'string' },
          asset: { type: 'string' },
          direzione: { type: 'string', enum: ['rialzista', 'ribassista', 'incerto'] },
        },
        required: ['titolo', 'direzione'],
      },
    },
  },
  required: ['angolo', 'catalizzatori'],
}

const IMPATTO = {
  type: 'object',
  properties: {
    rilevante: { type: 'boolean' },
    impatto_sul_book: { type: 'string' },
    sentinella: { type: 'string' },
  },
  required: ['rilevante', 'impatto_sul_book'],
}

const raccolto = await parallel(ANGOLI.map((a) => () =>
  agent(a.prompt, { label: `news:${a.key}`, phase: 'Raccolta', agentType: a.agent, schema: CATALIZZATORI })
))

// Dedup per titolo normalizzato (serve la vista completa → barriera giustificata).
const tutti = raccolto.filter(Boolean).flatMap((r) => (r.catalizzatori || []).map((c) => ({ ...c, angolo: r.angolo })))
const visti = new Set()
const unici = []
for (const c of tutti) {
  const k = (c.titolo || '').toLowerCase().replace(/\s+/g, ' ').trim().slice(0, 80)
  if (k && !visti.has(k)) { visti.add(k); unici.push(c) }
}

// Stima impatto sul book per ogni catalizzatore unico (risk-manager).
const conImpatto = await parallel(unici.map((c) => () =>
  agent(
    `Stima l'impatto sul book del bot (SOL/BTC/ETH, paper) di questo catalizzatore e indica se far ` +
    `scattare una sentinella (vedi cervello/sentinelle.md). Catalizzatore: ${JSON.stringify(c)}`,
    { label: 'impatto', phase: 'Impatto', schema: IMPATTO }
  ).then((i) => ({ ...c, ...i }))
))

const rilevanti = conImpatto.filter(Boolean).filter((c) => c.rilevante)

phase('Sintesi')
const digest = await agent(
  `Scrivi in italiano un digest news conciso: i 2-3 catalizzatori VERI (separa dal rumore), per ognuno ` +
  `direzione, asset, impatto sul book e l'eventuale sentinella da far scattare. ` +
  `Se nulla è rilevante, dillo chiaramente. Aggiungi il digest in fondo al log di oggi in ` +
  `Bot-Vault/90-Memoria-AI/news/ e, se c'è un catalizzatore ad alto impatto, segnala di allertare risk-manager. ` +
  `Catalizzatori rilevanti (JSON):\n${JSON.stringify(rilevanti, null, 2)}`,
  { label: 'digest', phase: 'Sintesi' }
)

log(`Scansione news: ${unici.length} catalizzatori unici, ${rilevanti.length} rilevanti.`)
return { unici: unici.length, rilevanti: rilevanti.length, digest }
