export const meta = {
  name: 'audit-strategia',
  description: 'Caccia agli edge deboli e agli sprechi di performance: ogni ipotesi verificata sui dati reali, niente overfitting spacciato per edge',
  whenToUse: 'Quando Nicola dice "audit strategia", "il nostro edge regge?", "caccia gli sprechi di performance".',
  phases: [
    { title: 'Ipotesi', detail: 'genera ipotesi di debolezza/spreco dell\'edge' },
    { title: 'Verifica', detail: 'ogni ipotesi verificata sui dati reali (research/, summary.json)' },
    { title: 'Sintesi', detail: 'verdetto onesto + leve a maggior ritorno' },
  ],
}

// Angoli da cui attaccare l'edge. Ognuno produce ipotesi falsificabili.
const ANGOLI = [
  { key: 'overfitting',  agent: 'backtest-engineer',
    prompt: 'Genera ipotesi di OVERFITTING della strategia principale: confronta in-sample vs out-of-sample in results/research/summary.json (es. SOL Calmar 1,97 IS vs 0,19 OOS). Dove l\'edge è troppo tarato? SOLA LETTURA.' },
  { key: 'generalizza',  agent: 'quant-strategist',
    prompt: 'Genera ipotesi sul fatto che l\'edge NON generalizzi: confronta i risultati su SOL vs BTC/ETH (summary.json, docs/validazione-1h-multiasset.md). È un edge o un caso fortunato su SOL? SOLA LETTURA.' },
  { key: 'costi',        agent: 'trader-esecuzione',
    prompt: 'Genera ipotesi su performance bruciata da costi/slippage: i backtest includono fee e slippage realistici? il turnover è alto? SOLA LETTURA.' },
  { key: 'rischio-resa', agent: 'risk-manager',
    prompt: 'Genera ipotesi su rendimento corretto per il rischio insufficiente: drawdown vs rendimento (Calmar), time-in-drawdown, code di perdita. SOLA LETTURA.' },
]

const IPOTESI = {
  type: 'object',
  properties: {
    angolo: { type: 'string' },
    ipotesi: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          testo: { type: 'string' },
          come_verificare: { type: 'string' },
          dato_di_riferimento: { type: 'string' },
        },
        required: ['testo', 'come_verificare'],
      },
    },
  },
  required: ['angolo', 'ipotesi'],
}

const ESITO = {
  type: 'object',
  properties: {
    confermata: { type: 'boolean' },
    numero_reale: { type: 'string' },
    conclusione: { type: 'string' },
  },
  required: ['confermata', 'conclusione'],
}

const risultati = await pipeline(
  ANGOLI,
  (a) => agent(a.prompt, { label: `ipotesi:${a.key}`, phase: 'Ipotesi', agentType: a.agent, schema: IPOTESI }),
  (gen, a) => parallel((gen?.ipotesi || []).map((h) => () =>
    agent(
      `Verifica questa ipotesi sui DATI REALI (results/research/summary.json, user_data/data_sources/, research/). ` +
      `Niente numeri inventati: se il dato non c'è, dillo. Ipotesi: ${h.testo}\nCome verificare: ${h.come_verificare}\n` +
      `Riferimento: ${h.dato_di_riferimento || 'n/d'}. SOLA LETTURA.`,
      { label: `verifica:${a.key}`, phase: 'Verifica', schema: ESITO }
    ).then((e) => ({ angolo: a.key, ipotesi: h.testo, esito: e }))
  ))
)

const verificate = risultati.flat().filter(Boolean)
const confermate = verificate.filter((v) => v.esito?.confermata)

phase('Sintesi')
const report = await agent(
  `Scrivi in italiano il verdetto onesto dell'audit strategia. ` +
  `Per ogni debolezza CONFERMATA: il numero reale che la prova e la conclusione. ` +
  `Poi le 2-3 LEVE a maggior ritorno per migliorare il rendimento corretto per il rischio (con colore 🟢🟡🔴). ` +
  `Sii brutalmente onesto: se l'edge regge solo su SOL/in-sample, scrivilo. ` +
  `Salva in consegne/audit/ con nome AAAA-MM-GG-audit-strategia.md (data di oggi). ` +
  `Ipotesi verificate (JSON):\n${JSON.stringify(verificate, null, 2)}`,
  { label: 'sintesi', phase: 'Sintesi' }
)

log(`Audit strategia: ${confermate.length}/${verificate.length} debolezze confermate.`)
return { confermate: confermate.length, totali: verificate.length, report }
