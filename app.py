import os
import time
from datetime import datetime

import openai
import streamlit as st

st.set_page_config(
    page_title="Chatbot com IA", page_icon="🤖", layout="centered"
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
    try:
        resposta_completa = gerar_resposta_com_retry(
            montar_mensagens_para_api(), placeholder
        )
        st.session_state.mensagens.append(
            {"role": "assistant", "content": resposta_completa}
        )
    except openai.AuthenticationError:
        st.error("Chave de API inválida ou expirada. Verifique o GROQ_API_KEY.")
    except openai.RateLimitError:
        st.error(
            f"Limite de requisições atingido mesmo após {MAX_TENTATIVAS} tentativas. "
            "Aguarde um pouco e tente novamente."
        )
    except openai.APIConnectionError:
        st.error(
            f"Não foi possível conectar à API da Groq após {MAX_TENTATIVAS} tentativas. "
            "Verifique sua conexão com a internet."
        )
    except openai.APIStatusError as e:
        st.error(f"A API da Groq retornou um erro (status {e.status_code}). Tente novamente.")
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado: {e}")


# Barra lateral: prompt de sistema, limpar conversa, regenerar e exportar
with st.sidebar:
    st.subheader("⚙️ Configurações")
    st.session_state.system_prompt = st.text_area(
        "Prompt de sistema",
        value=st.session_state.system_prompt,
        height=120,
        help=(
            "Instrução que define o comportamento do assistente. "
            "Clique fora do campo (ou pressione Ctrl+Enter) para confirmar a edição."
        ),
    )
    with st.expander("👁️ Prompt de sistema ativo no momento"):
        st.caption(st.session_state.system_prompt)

    st.divider()

    if st.button("🗑️ Limpar conversa"):
        st.session_state.mensagens = []
        st.rerun()

    ultima_e_do_assistente = (
        bool(st.session_state.mensagens)
        and st.session_state.mensagens[-1]["role"] == "assistant"
    )
    if st.button("🔁 Regenerar última resposta", disabled=not ultima_e_do_assistente):
        st.session_state.mensagens.pop()  # remove a resposta anterior
        st.session_state.regenerar = True
        st.rerun()

    if st.session_state.mensagens:
        st.download_button(
            label="💾 Exportar conversa (.txt)",
            data=montar_conversa_para_download(st.session_state.mensagens),
            file_name=f"conversa_{datetime.now():%Y%m%d_%H%M%S}.txt",
            mime="text/plain",
        )

# Exibe histórico de mensagens
for mensagem in st.session_state.mensagens:
    with st.chat_message(mensagem["role"]):
        st.markdown(mensagem["content"])

# Se o usuário pediu para regenerar, gera nova resposta para a última
# pergunta sem exigir uma nova entrada no chat_input.
if st.session_state.get("regenerar"):
    st.session_state.regenerar = False
    with st.chat_message("assistant"):
        placeholder = st.empty()
        responder(placeholder)
    st.rerun()

# Entrada de mensagem do usuário
entrada_usuario = st.chat_input(
    f"Digite sua mensagem... (máx. {MAX_CARACTERES_ENTRADA} caracteres)"
)

if entrada_usuario:
    caracteres_excedentes = len(entrada_usuario) - MAX_CARACTERES_ENTRADA
    if caracteres_excedentes > 0:
        st.warning(
            f"Sua mensagem tem {caracteres_excedentes} caracteres a mais que o "
            f"limite ({MAX_CARACTERES_ENTRADA}). Ela será cortada."
        )
    entrada_usuario = entrada_usuario.strip()[:MAX_CARACTERES_ENTRADA]

    if not entrada_usuario:
        st.warning("Mensagem vazia — digite algo antes de enviar.")
        st.stop()

    st.session_state.mensagens.append(
        {"role": "user", "content": entrada_usuario}
    )
    with st.chat_message("user"):
        st.markdown(entrada_usuario)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        responder(placeholder)