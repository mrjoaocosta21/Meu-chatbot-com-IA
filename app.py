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
SYSTEM_PROMPT = (
    "Você é um assistente virtual útil, educado e objetivo. "
    "Responda em português do Brasil, salvo pedido contrário."
)

# Verifica a chave no secrets.toml
if "GROQ_API_KEY" in st.secrets:
    cliente = openai.OpenAI(
        api_key=st.secrets["GROQ_API_KEY"],
        base_url="https://api.groq.com/openai/v1",
    )
else:
    st.error(
        "Chave GROQ_API_KEY não encontrada no arquivo .streamlit/secrets.toml!"
    )
    st.stop()

# Inicializa o histórico
if "mensagens" not in st.session_state:
    st.session_state.mensagens = []


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

    return resposta_completa


def montar_conversa_para_download(mensagens):
    """Monta um texto simples com a conversa para exportação."""
    linhas = [f"Conversa exportada em {datetime.now():%d/%m/%Y %H:%M}", "=" * 40, ""]
    for m in mensagens:
        autor = "Você" if m["role"] == "user" else "Assistente"
        linhas.append(f"{autor}: {m['content']}")
        linhas.append("")
    return "\n".join(linhas)


# Barra lateral: limpar conversa e exportar
with st.sidebar:
    if st.button("🗑️ Limpar conversa"):
        st.session_state.mensagens = []
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

# Entrada de mensagem do usuário
entrada_usuario = st.chat_input("Digite sua mensagem...")

if entrada_usuario:
    caracteres_excedentes = len(entrada_usuario) - MAX_CARACTERES_ENTRADA
    if caracteres_excedentes > 0:
        st.warning(
            f"Sua mensagem tem {caracteres_excedentes} caracteres a mais que o "
            f"limite ({MAX_CARACTERES_ENTRADA}). Ela será cortada."
        )
    entrada_usuario = entrada_usuario.strip()[:MAX_CARACTERES_ENTRADA]

    st.session_state.mensagens.append(
        {"role": "user", "content": entrada_usuario}
    )
    with st.chat_message("user"):
        st.markdown(entrada_usuario)

    # Trunca o histórico enviado à API (mantém as últimas N mensagens)
    historico_recente = st.session_state.mensagens[-MAX_MENSAGENS_HISTORICO:]
    mensagens_api = [{"role": "system", "content": SYSTEM_PROMPT}] + [
        {"role": m["role"], "content": m["content"]} for m in historico_recente
    ]

    with st.chat_message("assistant"):
        placeholder = st.empty()

        try:
            resposta_completa = gerar_resposta_com_retry(mensagens_api, placeholder)
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