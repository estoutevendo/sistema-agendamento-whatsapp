// Normalização de telefone e resolução de LID.
//
// O WhatsApp passou a identificar parte dos contatos por um "LID"
// (ex.: 137xxxxxxxxxxx@lid) em vez do número. Como o banco usa o telefone
// como chave da cliente, tudo é convertido para DDD + número (sem o 55)
// antes de chegar na API.

const fs = require('fs')
const path = require('path')

const ARQ_LID_MAP = path.join(__dirname, 'lid_map.json')
let lidMap = {}
try { lidMap = JSON.parse(fs.readFileSync(ARQ_LID_MAP, 'utf8')) } catch {}

function salvarLidMap() {
    try { fs.writeFileSync(ARQ_LID_MAP, JSON.stringify(lidMap, null, 2)) }
    catch (e) { console.error('Erro ao salvar lid_map.json:', e.message) }
}

// Só dígitos, sem o 55 quando sobra um número brasileiro
function normalizarTelefone(valor) {
    let d = String(valor || '').replace(/@.*$/, '').replace(/\D/g, '')
    if ((d.length === 12 || d.length === 13) && d.startsWith('55')) d = d.slice(2)
    return d
}

// DDD + 8 ou 9 dígitos
function ehTelefoneBR(d) {
    return /^[1-9]\d\d{8,9}$/.test(d || '')
}

// Chave de comparação: DDD + 8 últimos dígitos.
// Resolve o caso do mesmo número salvo com e sem o 9 na frente.
function chaveTel(t) {
    const d = normalizarTelefone(t)
    return d.length >= 10 ? d.slice(0, 2) + d.slice(-8) : d
}

async function resolverLid(client, lidOuJid) {
    const lid = String(lidOuJid).replace('@lid', '')
    if (lidMap[lid]) return lidMap[lid]

    const jid = `${lid}@lid`
    let tel = null

    // 1ª tentativa: API nova do whatsapp-web.js
    try {
        if (typeof client.getContactLidAndPhone === 'function') {
            const r = await client.getContactLidAndPhone([jid])
            const pn = Array.isArray(r) ? r[0]?.pn : null
            if (pn) tel = normalizarTelefone(pn)
        }
    } catch (e) {
        console.log('getContactLidAndPhone falhou:', e.message)
    }

    // 2ª tentativa: dados do contato
    if (!ehTelefoneBR(tel)) {
        try {
            const c = await client.getContactById(jid)
            tel = normalizarTelefone(c.number)
        } catch {}
    }

    if (ehTelefoneBR(tel)) {
        lidMap[lid] = tel  // cache em disco: não precisa resolver de novo
        salvarLidMap()
        return tel
    }
    return null
}

module.exports = { normalizarTelefone, ehTelefoneBR, chaveTel, resolverLid }
