import os
import time
from datetime import datetime

import openai
import streamlit as st

st.set_page_config(
    page_title="Chatbot com IA", page_icon="🤖", layout="centered"
)

# --- Estilos personalizados: bolhas de chat, indicador de digitação e
# limpeza visual (esconde o botão "Deploy", que não faz sentido para quem
# já está usando o app) ---
st.markdown(
    """
    <style>
    [data-testid="stAppDeployButton"] { display: none; }

    [data-testid="stChatMessageContent"][aria-label="Chat message from user"] {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        border-radius: 18px 18px 4px 18px;
        padding: 0.7rem 1rem;
    }
    [data-testid="stChatMessageContent"][aria-label="Chat message from user"] p {
        color: #ffffff;
        margin-bottom: 0;
    }
    [data-testid="stChatMessageContent"][aria-label="Chat message from assistant"] {
        background: var(--secondary-background-color, rgba(128, 128, 128, 0.1));
        border-radius: 18px 18px 18px 4px;
        padding: 0.7rem 1rem;
    }
    .horario-mensagem {
        font-size: 0.72rem;
        opacity: 0.55;
        margin-top: 0.15rem;
    }
    .pontos-digitando span {
        animation: piscar 1.4s infinite both;
        font-size: 1.3rem;
        line-height: 1;
    }
    .pontos-digitando span:nth-child(2) { animation-delay: 0.2s; }
    .pontos-digitando span:nth-child(3) { animation-delay: 0.4s; }
    @keyframes piscar {
        0%, 80%, 100% { opacity: 0.2; }
        40% { opacity: 1; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🤖 Chatbot com IA")
st.caption("Seu assistente inteligente alimentado pelo Llama 3 (Groq)")

# --- Configurações ---
MODELO = st.secrets.get("GROQ_MODEL", "llama-3.3-70b-versatile")
MAX_MENSAGENS_HISTORICO = 20  # limita o contexto enviado à API
MAX_CARACTERES_ENTRADA = 4000
MAX_TENTATIVAS = 3  # tentativas para erros transitórios (retry automático)
SYSTEM_PROMPT_PADRAO = (
    "Você é um assistente virtual útil, educado e objetivo. "
    "Responda em português do Brasil, salvo pedido contrário."
)
AVATAR_USUARIO = "🧑"
AVATAR_ASSISTENTE = "🤖"
SUGESTOES_INICIAIS = [
    "Explique um conceito complexo de forma simples",
    "Me ajude a escrever um e-mail profissional",
    "Dê ideias criativas para um projeto",
    "Resuma um texto que vou colar em seguida",
]

# Busca a chave primeiro no secrets.toml (uso local/Streamlit Cloud) e,
# se não encontrar, cai para variável de ambiente (útil em outros
# provedores de deploy, como Render, Docker, etc.)
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")

if GROQ_API_KEY:
    cliente = openai.OpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )
else:
    st.error(
        "Chave GROQ_API_KEY não encontrada. Defina-a em "
        ".streamlit/secrets.toml ou como variável de ambiente."
    )
    st.stop()

# Inicializa o histórico e o prompt de sistema (editável)
if "mensagens" not in st.session_state:
    st.session_state.mensagens = []
if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = SYSTEM_PROMPT_PADRAO
if "proximo_id_mensagem" not in st.session_state:
    st.session_state.proximo_id_mensagem = 0


def adicionar_mensagem(role, content):
    """Adiciona uma mensagem ao histórico com id único e horário,
    usados para exibir o horário e o botão de feedback (👍/👎)."""
    mensagem = {
        "id": st.session_state.proximo_id_mensagem,
        "role": role,
        "content": content,
        "hora": datetime.now().strftime("%H:%M"),
    }
    st.session_state.proximo_id_mensagem += 1
    st.session_state.mensagens.append(mensagem)


def gerar_resposta_com_retry(mensagens_api, placeholder):
    """
    Chama a API com streaming e tenta novamente automaticamente em erros
    transitórios (rate limit, conexão, erro 5xx da API), usando backoff
    exponencial entre as tentativas.
    """
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        resposta_completa = ""
        try:
            stream = cliente.chat.completions.create(
                model=MODELO,
                messages=mensagens_api,
                stream=True,
            )
            for chunk in stream:
                # Alguns provedores enviam um chunk final sem "choices"
                # (ex.: chunk apenas com estatísticas de uso); ignorá-lo
                # evita um IndexError ao acessar choices[0].
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    resposta_completa += delta
                    placeholder.markdown(resposta_completa + "▌")

            placeholder.markdown(resposta_completa)
            return resposta_completa

        except (openai.RateLimitError, openai.APIConnectionError) as e:
            if tentativa == MAX_TENTATIVAS:
                raise
            espera = 2 ** tentativa  # backoff exponencial: 2s, 4s, 8s...
            placeholder.markdown(
                f"⏳ Tentativa {tentativa} falhou ({type(e).__name__}). "
                f"Tentando novamente em {espera}s..."
            )
            time.sleep(espera)

        except openai.APIStatusError as e:
            # Só tenta de novo em erros de servidor (5xx); erros 4xx não adianta repetir
            if e.status_code < 500 or tentativa == MAX_TENTATIVAS:
                raise
            espera = 2 ** tentativa
            placeholder.markdown(
                f"⏳ Tentativa {tentativa} falhou (status {e.status_code}). "
                f"Tentando novamente em {espera}s..."
            )
            time.sleep(espera)


def montar_conversa_para_download(mensagens):
    """Monta um texto simples com a conversa para exportação."""
    linhas = [f"Conversa exportada em {datetime.now():%d/%m/%Y %H:%M}", "=" * 40, ""]
    for m in mensagens:
        autor = "Você" if m["role"] == "user" else "Assistente"
        linhas.append(f"{autor}: {m['content']}")
        linhas.append("")
    return "\n".join(linhas)


def montar_mensagens_para_api():
    """Monta a lista de mensagens (com system prompt) a enviar à API,
    truncando o histórico para não estourar o contexto."""
    historico_recente = st.session_state.mensagens[-MAX_MENSAGENS_HISTORICO:]
    return [{"role": "system", "content": st.session_state.system_prompt}] + [
        {"role": m["role"], "content": m["content"]} for m in historico_recente
    ]


def responder(placeholder):
    """Chama a API, trata erros e adiciona a resposta ao histórico."""
    placeholder.markdown(
        '<span class="pontos-digitando">Pensando <span>.</span><span>.</span><span>.</span></span>',
        unsafe_allow_html=True,
    )
    try:
        resposta_completa = gerar_resposta_com_retry(
            montar_mensagens_para_api(), placeholder
        )
        adicionar_mensagem("assistant", resposta_completa)
    except openai.AuthenticationError:
        placeholder.empty()
        st.error("Chave de API inválida ou expirada. Verifique o GROQ_API_KEY.")
    except openai.RateLimitError:
        placeholder.empty()
        st.error(
            f"Limite de requisições atingido mesmo após {MAX_TENTATIVAS} tentativas. "
            "Aguarde um pouco e tente novamente."
        )
    except openai.APIConnectionError:
        placeholder.empty()
        st.error(
            f"Não foi possível conectar à API da Groq após {MAX_TENTATIVAS} tentativas. "
            "Verifique sua conexão com a internet."
        )
    except openai.APIStatusError as e:
        placeholder.empty()
        st.error(f"A API da Groq retornou um erro (status {e.status_code}). Tente novamente.")
    except Exception as e:
        placeholder.empty()
        st.error(f"Ocorreu um erro inesperado: {e}")


@st.dialog("Limpar conversa?")
def confirmar_limpeza():
    st.write(
        "Isso vai apagar todo o histórico da conversa atual. "
        "Essa ação não pode ser desfeita."
    )
    col_cancelar, col_confirmar = st.columns(2)
    with col_cancelar:
        if st.button("Cancelar", use_container_width=True):
            st.rerun()
    with col_confirmar:
        if st.button("Sim, limpar", type="primary", use_container_width=True):
            st.session_state.mensagens = []
            st.session_state.toast_pendente = "🗑️ Conversa limpa com sucesso!"
            st.rerun()


# Barra lateral: ações rápidas em destaque, configurações avançadas escondidas
with st.sidebar:
    st.subheader("💬 Conversa")

    col_limpar, col_regenerar = st.columns(2)
    with col_limpar:
        if st.button("🗑️ Limpar", use_container_width=True, disabled=not st.session_state.mensagens):
            confirmar_limpeza()

    ultima_e_do_assistente = (
        bool(st.session_state.mensagens)
        and st.session_state.mensagens[-1]["role"] == "assistant"
    )
    with col_regenerar:
        if st.button("🔁 Regenerar", use_container_width=True, disabled=not ultima_e_do_assistente):
            st.session_state.mensagens.pop()  # remove a resposta anterior
            st.session_state.regenerar = True
            st.rerun()

    st.download_button(
        label="💾 Exportar conversa (.txt)",
        data=montar_conversa_para_download(st.session_state.mensagens),
        file_name=f"conversa_{datetime.now():%Y%m%d_%H%M%S}.txt",
        mime="text/plain",
        use_container_width=True,
        disabled=not st.session_state.mensagens,
    )

    st.divider()

    with st.expander("⚙️ Configurações avançadas"):
        st.session_state.system_prompt = st.text_area(
            "Prompt de sistema",
            value=st.session_state.system_prompt,
            height=120,
            help=(
                "Instrução que define o comportamento do assistente. "
                "Clique fora do campo (ou pressione Ctrl+Enter) para confirmar a edição."
            ),
        )
        st.caption("Prompt ativo no momento:")
        st.caption(f"_{st.session_state.system_prompt}_")

    st.caption(f"Modelo em uso: `{MODELO}`")

# Mensagem que será processada nesta execução (vinda do chat_input ou de um
# clique numa sugestão inicial) — resolvida antes de decidir o que exibir,
# para não mostrar a tela de boas-vindas e a resposta ao mesmo tempo.
mensagem_pendente = st.session_state.pop("mensagem_pendente", None)

# Exibe um toast pendente de uma ação da execução anterior (ex.: limpar
# conversa), já que st.toast precisa ser chamado após o st.rerun() que
# disparou a ação para aparecer corretamente.
toast_pendente = st.session_state.pop("toast_pendente", None)
if toast_pendente:
    st.toast(toast_pendente)

# Tela de boas-vindas com sugestões, exibida só quando a conversa está vazia
if not st.session_state.mensagens and not mensagem_pendente and not st.session_state.get("regenerar"):
    st.markdown("#### 👋 Como posso ajudar você hoje?")
    st.caption("Escolha uma sugestão abaixo ou digite sua própria pergunta.")
    colunas = st.columns(2)
    for indice, sugestao in enumerate(SUGESTOES_INICIAIS):
        with colunas[indice % 2]:
            if st.button(sugestao, use_container_width=True, key=f"sugestao_{indice}"):
                st.session_state.mensagem_pendente = sugestao
                st.rerun()

# Exibe histórico de mensagens
for mensagem in st.session_state.mensagens:
    avatar = AVATAR_USUARIO if mensagem["role"] == "user" else AVATAR_ASSISTENTE
    with st.chat_message(mensagem["role"], avatar=avatar):
        st.markdown(mensagem["content"])
        rodape_esquerda, rodape_direita = st.columns([3, 1])
        with rodape_esquerda:
            if mensagem.get("hora"):
                st.markdown(
                    f'<div class="horario-mensagem">{mensagem["hora"]}</div>',
                    unsafe_allow_html=True,
                )
        if mensagem["role"] == "assistant":
            with rodape_direita:
                st.feedback("thumbs", key=f"feedback_{mensagem['id']}")

# Se o usuário pediu para regenerar, gera nova resposta para a última
# pergunta sem exigir uma nova entrada no chat_input.
if st.session_state.get("regenerar"):
    st.session_state.regenerar = False
    with st.chat_message("assistant", avatar=AVATAR_ASSISTENTE):
        placeholder = st.empty()
        responder(placeholder)
    st.rerun()

# Entrada de mensagem do usuário
entrada_usuario = st.chat_input(
    f"Digite sua mensagem... (máx. {MAX_CARACTERES_ENTRADA} caracteres)"
)

nova_mensagem = mensagem_pendente or entrada_usuario

if nova_mensagem:
    caracteres_excedentes = len(nova_mensagem) - MAX_CARACTERES_ENTRADA
    if caracteres_excedentes > 0:
        st.warning(
            f"Sua mensagem tem {caracteres_excedentes} caracteres a mais que o "
            f"limite ({MAX_CARACTERES_ENTRADA}). Ela será cortada."
        )
    nova_mensagem = nova_mensagem.strip()[:MAX_CARACTERES_ENTRADA]

    if not nova_mensagem:
        st.warning("Mensagem vazia — digite algo antes de enviar.")
        st.stop()

    adicionar_mensagem("user", nova_mensagem)
    with st.chat_message("user", avatar=AVATAR_USUARIO):
        st.markdown(nova_mensagem)

    with st.chat_message("assistant", avatar=AVATAR_ASSISTENTE):
        placeholder = st.empty()
        responder(placeholder)

    # Rerun para exibir a nova mensagem pelo mesmo caminho do histórico
    # (com horário e botão de feedback 👍/👎), igual às mensagens antigas.
    st.rerun()