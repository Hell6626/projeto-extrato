import os
from flask import Flask, render_template, request, jsonify, send_file
import io
import tempfile
import logging

# Supondo que suas funções estejam definidas corretamente
from Bancos import (
    extract_sicoob, 
    extract_sicredi, 
    extract_caixa, 
    extract_bradesco, 
    extract_cseis,
    extract_banco_do_brasil
)

# Configuração de logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# Configurações do app
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process_pdf', methods=['POST'])
def process_pdf():
    app.logger.info("Process PDF route called")
    
    # Verifica se há um arquivo na requisição
    if 'file' not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado."}), 400

    # Obtém o arquivo enviado
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Nenhum arquivo selecionado."}), 400

    # Validar extensão do arquivo
    if not allowed_file(file.filename):
        return jsonify({"error": "Tipo de arquivo não permitido."}), 400

    # Obtém parâmetros opcionais
    banco = request.form.get('banco', '').strip().lower()
    cabecalho = request.form.get('cabecalho', '')
    mes = request.form.get('mes')
    ano = request.form.get('ano')

    # Criar o cabeçalho se necessário
    if not cabecalho:
        cabecalho = f"Competencia;01/{mes}/{ano};Conta Banco;{request.form.get('conta_banco', '')};Saldo Inicial;{request.form.get('saldo_inicial', '')}\n"

    # Lê o conteúdo do arquivo PDF
    pdf_content = file.read()

    # Escolhe a função apropriada com base no banco selecionado
    try:
        if banco == "bradesco":
            result, _ = extract_bradesco(pdf_content, cabecalho, mes, ano)
        elif banco == "caixa":
            result = extract_caixa(pdf_content, cabecalho)
        elif banco == "c6":
            result = extract_cseis(pdf_content, cabecalho)
        elif banco == "sicoob":
            result = extract_sicoob(pdf_content, cabecalho, ano)
        elif banco == "sicredi":
            result = extract_sicredi(pdf_content, cabecalho)
        elif banco == "banco do brasil":
            result = extract_banco_do_brasil(pdf_content, cabecalho)
        else:
            return jsonify({"error": "Banco não suportado ou não especificado."}), 400

        # Retorna o resultado processado em um arquivo
        temp_file = io.BytesIO(result.encode())

        return send_file(
            temp_file,
            as_attachment=True,
            download_name=f"{banco}_output.txt",
            mimetype='text/plain'
        )

    except Exception as e:
        app.logger.error(f"Error processing PDF: {str(e)}")
        return jsonify({"error": f"Erro ao processar o PDF: {str(e)}"}), 500

# Remova o bloco if __name__ == '__main__'
# if __name__ == '__main__':
#     app.run(host="0.0.0.0", port=5000, debug=True)