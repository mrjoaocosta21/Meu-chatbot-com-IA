# VISÃO GERAL
Este projeto é um chatbot com IA que responde a perguntas dos usuários em linguagem natural, utilizando o modelo **Llama 3.3 70B**, servido pela **API da Groq** (compatível com o SDK da OpenAI). Ele mantém o histórico da conversa, exibe as respostas em tempo real via streaming e fornece respostas inteligentes e úteis.

# RECURSOS
- Conversas naturais movidas por IA;
- Integração com o modelo Llama 3.3 (via API da Groq, compatível com OpenAI SDK);
- Respostas em tempo real com efeito de digitação (streaming);
- Memória do histórico de conversas, com limite automático das últimas mensagens para não estourar o contexto;
- **Prompt de sistema editável** diretamente pela barra lateral, sem precisar mexer no código;
- Botão para limpar a conversa a qualquer momento;
- **Botão para regenerar** a última resposta do assistente;
- **Exportação da conversa** em arquivo `.txt`, com data e hora;
- **Retry automático** com backoff exponencial em falhas transitórias da API (rate limit, conexão, erros 5xx);
- Aviso de limite de caracteres na mensagem antes do corte automático, além de bloqueio de envio de mensagens vazias;
- Chave de API lida do `secrets.toml` ou, como alternativa, de uma **variável de ambiente** `GROQ_API_KEY` (útil para deploy em Render, Docker, etc.);
- Interface limpa via Streamlit;
- Tratamento de erros específico (autenticação, limite de requisições, conexão, erros da API) e proteção contra respostas de streaming malformadas;
- Dependências com **versões fixadas** em `requirements.txt` para builds reprodutíveis.

# TECNOLOGIAS UTILIZADAS
- Python 3
- Streamlit (Framework Web) — versão fixada em `1.61.1`
- Groq API (via SDK da OpenAI, usando `base_url` customizado) — SDK `openai` fixado em `2.54.0`
- Modelo Llama 3.3 70B (`llama-3.3-70b-versatile`)

# COMO FUNCIONA
1. O usuário digita uma mensagem;
2. A mensagem é adicionada ao histórico e enviada, junto com o prompt de sistema (padrão ou personalizado na barra lateral) e as últimas mensagens da conversa, para a API da Groq;
3. A IA gera a resposta, que é exibida progressivamente na tela (streaming);
4. O histórico da conversa é armazenado na sessão do Streamlit (`session_state`);
5. O usuário pode limpar a conversa, regenerar a última resposta ou exportar a conversa a qualquer momento pela barra lateral.

# COMO EXECUTAR O PROJETO
1. Instale o Python 3.x;
2. Instale os pacotes necessários:
   ```
   pip install -r requirements.txt
   ```
3. Defina sua chave da Groq de uma das duas formas:
   - Crie o arquivo `.streamlit/secrets.toml` na raiz do projeto:
     ```toml
     GROQ_API_KEY = "sua-chave-api-groq"
     # Opcional: sobrescreve o modelo padrão (llama-3.3-70b-versatile)
     # GROQ_MODEL = "llama-3.3-70b-versatile"
     ```
     ⚠️ Nunca compartilhe ou versione esse arquivo — ele contém uma chave secreta.
   - **Ou** defina a variável de ambiente `GROQ_API_KEY` (recomendado em Docker, Render, etc.):
     ```
     export GROQ_API_KEY="sua-chave-api-groq"
     ```
4. Execute a aplicação:
   ```
   streamlit run app.py
   ```
5. Abra no seu navegador (geralmente em `http://localhost:8501`).

# POSSÍVEIS MELHORIAS
- Adicionar entrada de voz e saída de áudio;
- Salvar conversas em um banco de dados (ex.: SQLite), em vez de depender apenas do `session_state`;
- Adicionar autenticação de usuários;
- Dar suporte para entrada de arquivos e imagens (exigiria trocar de modelo, já que o Llama 3.3 70B via Groq é somente texto);
- Fazer o deploy na nuvem (AWS, Render, Streamlit Community Cloud);
- Adicionar suporte a múltiplos idiomas na interface;
- Adicionar botões de feedback (👍/👎) nas respostas do assistente.