// Trecho do bot (whatsapp-web.js): fluxo de agendamento.
// A conversa é uma máquina de estados simples; a etapa atual de cada
// cliente fica salva na API, então o bot pode reiniciar sem perder nada.
//
// Menu, cancelamento, área administrativa e lembretes ficaram de fora.

const axios = require('axios')

const API = process.env.API_URL || 'http://127.0.0.1:8000'
const NUMERO_AVISOS = process.env.NUMERO_AVISOS // quem recebe o aviso de novo horário

const sessoes = {}

async function carregarSessao(telefone) {
    try {
        const { data } = await axios.get(`${API}/sessoes/${telefone}`)
        sessoes[telefone] = data
    } catch {
        sessoes[telefone] = { etapa: 'menu' }
    }
    return sessoes[telefone]
}

async function salvarSessao(telefone) {
    try {
        await axios.post(`${API}/sessoes/${telefone}`, sessoes[telefone])
    } catch (err) {
        console.error('Erro ao salvar sessão:', err.message)
    }
}

async function fluxoAgendamento(client, msg, telefone, texto, sessao) {
    if (sessao.etapa === 'agendar_nome') {
        sessao.nome = texto
        sessao.etapa = 'agendar_servico'

        const { data: servicos } = await axios.get(`${API}/servicos`)
        let resposta = `Olá *${texto}*! 😊\n\nQual serviço deseja?\n\n`
        servicos.forEach(s => { resposta += `*${s.id}.* ${s.nome} - R$ ${s.preco}\n` })
        resposta += '\n_Digite *cancelar* a qualquer momento para voltar ao menu._'
        return msg.reply(resposta)
    }

    if (sessao.etapa === 'agendar_servico') {
        sessao.servico_id = parseInt(texto)
        sessao.etapa = 'agendar_data'
        return msg.reply('📅 Qual data? Digite no formato *DD/MM/AAAA*')
    }

    if (sessao.etapa === 'agendar_data') {
        try {
            const { data } = await axios.get(`${API}/horarios-disponiveis?data=${texto}`)
            if (!data.horarios.length) {
                return msg.reply('😔 Não há horários livres nessa data. Escolha outra:')
            }

            sessao.data_escolhida = texto
            sessao.horarios_disponiveis = data.horarios
            sessao.etapa = 'agendar_horario'

            const lista = data.horarios.map((h, i) => `*${i + 1}.* ${h}`).join('\n')
            return msg.reply(`📅 *Horários para ${texto}:*\n\n${lista}\n\nDigite o número do horário.`)
        } catch (err) {
            // A API já devolve a mensagem certa (domingo, feriado, dia fechado...)
            const motivo = err.response?.data?.detail || 'Data inválida.'
            return msg.reply(`❌ ${motivo}\n\nTente outra data:`)
        }
    }

    if (sessao.etapa === 'agendar_horario') {
        const i = parseInt(texto) - 1
        if (isNaN(i) || i < 0 || i >= sessao.horarios_disponiveis.length) {
            return msg.reply('❌ Opção inválida. Digite o número do horário:')
        }

        const [dia, mes, ano] = sessao.data_escolhida.split('/')
        const data_hora = `${ano}-${mes}-${dia}T${sessao.horarios_disponiveis[i]}:00`

        try {
            await axios.post(`${API}/clientes`, { nome: sessao.nome, telefone })
            const { data: ag } = await axios.post(`${API}/agendamentos`, {
                telefone,
                servico_id: sessao.servico_id,
                data_hora,
            })
            sessao.etapa = 'menu'

            const quando = new Date(ag.data_hora).toLocaleString('pt-BR')

            // Aviso para a profissional; se falhar, não atrapalha a cliente
            if (NUMERO_AVISOS) {
                client.sendMessage(`${NUMERO_AVISOS}@c.us`,
                    `🔔 *Novo agendamento*\n${ag.cliente.nome} · ${ag.servico.nome}\n📅 ${quando}`
                ).catch(e => console.error('Aviso não enviado:', e.message))
            }

            return msg.reply(
                '✅ *Agendamento confirmado!*\n\n' +
                `✂️ ${ag.servico.nome}\n📅 ${quando}\n💰 R$ ${ag.servico.preco}\n\n` +
                'Na véspera você recebe um lembrete para confirmar.'
            )
        } catch (err) {
            sessao.etapa = 'menu'
            const motivo = err.response?.data?.detail || 'Não foi possível agendar.'
            return msg.reply(`❌ ${motivo}\n\nDigite *0* para voltar ao menu.`)
        }
    }
}

module.exports = { carregarSessao, salvarSessao, fluxoAgendamento }
