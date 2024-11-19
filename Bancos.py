import re
import pytesseract
import pdfplumber
import io
import fitz  # PyMuPDF
import unicodedata
import cv2
import numpy as np
from PIL import Image
from pdf2image import convert_from_bytes
from PyPDF2 import PdfReader


def preprocess_image(image):
    image = np.array(image)
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized_image = cv2.resize(gray_image, (0, 0), fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, binary_image = cv2.threshold(resized_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    denoised_image = cv2.medianBlur(binary_image, 5)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced_image = clahe.apply(denoised_image)
    final_image = Image.fromarray(enhanced_image)
    
    return final_image

def extract_bradesco(pdf_content, cabecalho, mes, ano):
    print("Processando extrato do Bradesco")
    
    images = convert_from_bytes(pdf_content)
    
    extracted_text = []
    for img in images:
        processed_img = preprocess_image(img)
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,-/ '
        text = pytesseract.image_to_string(processed_img, lang='por', config=custom_config)
        extracted_text.append(text)
    
    full_text = "\n".join(extracted_text)
    
    lines = full_text.split('\n')
    processed_lines = []
    ignored_lines = []
    current_date = ""
    
    for line in lines:
        if "saldo" in line.lower():
            ignored_lines.append(line)
            continue

        date_match = re.match(r'^(\d{2})', line)
        if date_match and date_match.group(1) != "00":
            current_date = date_match.group(1)
        
        if current_date:
            match = re.match(r'(?:\d{2}\s+)?(\d{2}/\d{2}/\d{4}|\S.+?)\s+(\d{7})?\s*([\d.,]+\s?-?)?$', line)
            if match:
                historico_ou_data, n_doc, valor = match.groups()
                
                if re.match(r'\d{2}/\d{2}/\d{4}', historico_ou_data) or not historico_ou_data.strip():
                    ignored_lines.append(line)
                    continue

                historico = historico_ou_data.strip()

                n_doc = n_doc if n_doc else ''
                valor = valor.replace(" ", "") if valor else ''
                
                if valor.endswith('-'):
                    valor_debito = valor[:-1].replace('.', '')
                    valor_credito = ''
                else:
                    valor_credito = valor.replace('.', '')
                    valor_debito = ''
                
                processed_line = f"{current_date}/{mes}/{ano};{historico};{n_doc};{valor_credito};{valor_debito};"
                processed_lines.append(processed_line)
            else:
                ignored_lines.append(line)
        else:
            ignored_lines.append(line)
    
    result = cabecalho + "\n" + "\n".join(processed_lines)
    error_result = "Linhas ignoradas:\n" + "\n".join(ignored_lines)
    
    return result, error_result

def extract_caixa(pdf_content, cabecalho):
    print("caixa")
    date_pattern = re.compile(r"^\s*\d{2}/\d{2}/\d{4}")
    exclude_phrase = "SALDO DIA"
    data_pattern = re.compile(r"(\d{2}/\d{2}/\d{4})\s+(\d{6})\s+(.+?)\s+([\d.,]+)\s+([CD])")

    pdf_file = io.BytesIO(pdf_content)
    with fitz.open(stream=pdf_file, filetype="pdf") as doc:
        formatted_lines = [cabecalho]
        for page in doc:
            text = page.get_text()
            for line in text.split('\n'):
                if date_pattern.match(line) and exclude_phrase not in line:
                    match = data_pattern.search(line)
                    if match:
                        amount = match.group(4).replace('.', '')
                        if match.group(5) == 'C':
                            formatted_line = ';'.join([match.group(1), match.group(3), match.group(2), amount, '', ''])
                        else:
                            formatted_line = ';'.join([match.group(1), match.group(3), match.group(2), '', amount,])
                        formatted_lines.append(formatted_line)
    
    return '\n'.join(formatted_lines)

def extract_cseis(pdf_content, cabecalho):
    print("c6")
    date_pattern = re.compile(r'^(\d{2}/\d{2}/\d{4})')
    historico_pattern = re.compile(r'(.+?)(?=\w+?\d{11}\s)')
    doc_pattern = re.compile(r'(\d{11})')
    valor_pattern = re.compile(r'(\d{1,3}(?:\.\d{3})*,\d{2})\s([DC])')
    
    pdf_file = io.BytesIO(pdf_content)
    with pdfplumber.open(pdf_file) as pdf:
        output_lines = [cabecalho]
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines = text.split('\n')
                for line in lines:
                    date_match = date_pattern.search(line)
                    if date_match:
                        rest_of_line = line[date_match.end():].strip()
                        historico_match = historico_pattern.search(rest_of_line)
                        if not historico_match:
                            print(f"Campo 'historico' não encontrado: {line}")
                            continue
                        
                        rest_of_line = rest_of_line[historico_match.end():].strip()
                        
                        doc_match = doc_pattern.search(rest_of_line)
                        if not doc_match:
                            print(f"Campo 'nº doc' não encontrado: {line}")
                            continue
                        
                        rest_of_line = rest_of_line[doc_match.end():].strip()
                        
                        valor_match = valor_pattern.search(rest_of_line)
                        if not valor_match:
                            print(f"Campo 'valor' não encontrado: {line}")
                            continue
                        
                        valor_formatado = valor_match.group(1).replace('.', '')
                        
                        output_line = f"{date_match.group(1)};{historico_match.group(0)};{doc_match.group(1)};"
                        if valor_match.group(2) == 'D':
                            output_line += f";{valor_formatado};"
                        else:
                            output_line += f"{valor_formatado};;"
                        
                        output_lines.append(output_line)
    
    return '\n'.join(output_lines)

def remover_acentos(texto):
    texto_normalizado = unicodedata.normalize('NFD', texto)
    return re.sub(r'[\u0300-\u036f]', '', texto_normalizado)

def is_debit(value_indicator):
    return value_indicator == 'D'

def sicoob_banco(pdf_content):
    print("extrato enviado pelo banco?")
    pdf_file = io.BytesIO(pdf_content)
    reader = PdfReader(pdf_file)
    extracted_text = [page.extract_text() for page in reader.pages]

    pattern = r'(\d{2}/\d{2}/\d{4})\s*(\S*)?\s*([\wáéíóúÁÉÍÓÚàèìòùÀÈÌÒÙäëïöüÄËÏÖÜãñõÃÑÕçÇ\s/\-.]+)\s+(\d{1,3}(?:\.\d{3})*,\d{2}[DC])'

    entries = []

    for page_text in extracted_text:
        matches = re.findall(pattern, page_text, re.DOTALL)
        entries.extend(matches)

    formatted_txt_lines = [
        'Data;Historico;Documento;Valor Credito (Subtrai);Valor Debito (Soma);\n'
    ]

    for entry in entries:
        date, code, description, value = entry[:4]
        value_indicator = value[-1]

        description = remover_acentos(description)

        amount = value[:-1].replace('.', '')

        if is_debit(value_indicator):
            line = f"{date};{description};{code};;{amount};\n"
        else:
            line = f"{date};{description};{code};{amount};;\n"
        formatted_txt_lines.append(line)

    return ''.join(formatted_txt_lines)
def sicoob_cliente(pdf_content, ano):
    print("extrato enviado pelo cliente")
    pdf_file = io.BytesIO(pdf_content)
    reader = PdfReader(pdf_file)
    
    formatted_txt_lines = [
        'Data;Historico;Documento;Valor Credito (Subtrai);Valor Debito (Soma);\n'
    ]
    
    for page in reader.pages:
        texto = page.extract_text()
        
        linhas = re.split(r'(?=\d{2}/\d{2})', texto)
        
        for linha in linhas:
            linha = linha.strip()
            if linha and re.match(r'\d{2}/\d{2}', linha):
                componentes = re.match(r'(\d{2}/\d{2})(.+?)(\d{1,3}(?:\.\d{3})*,\d{2}[CD])(.+)', linha)
                if componentes:
                    data = componentes.group(1)
                    historico = componentes.group(2)
                    valor = componentes.group(3)
                    documento = componentes.group(4)
                    
                    match_valor = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2}[CD])$', historico + valor)
                    if match_valor:
                        valor_completo = match_valor.group(1)
                        historico = (historico + valor)[:-(len(valor_completo))]
                        valor = valor_completo.replace(".", "")
                    
                    if "SALDO DO DIA" not in historico.upper():
                        if valor.endswith('C'):
                            linha_formatada = f"{data.strip()}/{ano};{historico.strip()};{documento.strip()};{valor.strip()[:-1]};;\n"
                        elif valor.endswith('D'):
                            linha_formatada = f"{data.strip()}/{ano};{historico.strip()};{documento.strip()};;{valor.strip()[:-1]};\n"
                        else:
                            linha_formatada = f"linha não sem valor:\n{data.strip()}/{ano};{historico.strip()};{documento.strip()};{valor.strip()}\n"
                        
                        formatted_txt_lines.append(linha_formatada)

    return ''.join(formatted_txt_lines)
def extract_sicoob(pdf_content, cabecalho, ano):
    # Tenta primeiro com sicoob_banco
    resultado_banco = sicoob_banco(pdf_content)
    linhas_banco = resultado_banco.count('\n')
    
    # Se sicoob_banco produziu 1 ou menos linhas (apenas o cabeçalho), usa sicoob_cliente
    if linhas_banco <= 1:
        resultado_cliente = sicoob_cliente(pdf_content, ano)
        return cabecalho + resultado_cliente
    else:
        return cabecalho + resultado_banco

def extract_sicredi(pdf_content, cabecalho):
    print("Sicredi")
    try:
        # Cria um objeto BytesIO a partir do conteúdo PDF
        arquivo_pdf = io.BytesIO(pdf_content)
        leitor_pdf = PdfReader(arquivo_pdf)
        texto_completo = ""
        for pagina in range(len(leitor_pdf.pages)):
            texto = leitor_pdf.pages[pagina].extract_text()
            if texto:
                texto_completo += texto
            else:
                print(f"Aviso: Nenhum texto extraído da página {pagina + 1}.")

        # Formatar as transações
        transacoes = texto_completo.splitlines()
        transacoes_formatadas = []

        # Expressão regular para validar o formato da data
        padrao_data = re.compile(r"\d{2}/\d{2}/\d{4}")

        for transacao in transacoes:
            # Extrair cada parte da linha com base nos tamanhos especificados
            data = transacao[:13].strip()
            codigo = transacao[13:24].strip()
            historico = transacao[24:72].strip()
            debito = transacao[72:92].strip().replace(".", "")
            credito = transacao[92:112].strip().replace(".", "")
            saldo = transacao[112:132].strip()

            # Verificar se o campo de data está no formato correto
            if padrao_data.fullmatch(data):
                # Formatar a linha
                transacao_formatada = f"{data} ; {historico} ; {codigo} ; {credito} ; {debito} ; ;"
                transacoes_formatadas.append(transacao_formatada)

        # Criar a string de saída
        resultado = cabecalho
        for transacao in transacoes_formatadas:
            resultado += transacao + '\n'
            
        return resultado

    except Exception as e:
        print(f"Ocorreu um erro: {e}")
        return None

def extract_banco_do_brasil(pdf_content, cabecalho):
    print("Processando extrato do Banco do Brasil")
    
    # Lê o conteúdo do PDF a partir de um objeto BytesIO
    pdf_file = io.BytesIO(pdf_content)
    pdf_reader = PdfReader(pdf_file)
    all_text = "".join(page.extract_text() or '' for page in pdf_reader.pages)

    lines = all_text.split('\n')
    
    # Padrões de regex para tentar
    padrao1 = re.compile(r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*(\(\-\)|\(\+\))\s*(\d{2}/\d{2}/\d{4})\s*(\d+)\s*(\d+)\s*(.*)")
    padrao2 = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2})\s*(\(\-\)|\(\+\))\s*(\d{2}/\d{2}/\d{4})\s*(.*)")

    linhas_processadas = []

    for linha in lines:
        # Ignorar linhas com "Saldo Anterior" ou "S A L D O"
        if "Saldo Anterior" in linha or "S A L D O" in linha:
            continue
        
        # Teste para o primeiro padrão
        correspondencia1 = padrao1.match(linha)
        if correspondencia1:
            valor, sinal, data, lote, documento, historico = correspondencia1.groups()
            # Remover acentos de cada campo
            historico = remover_acentos(historico)
            documento = remover_acentos(documento)
            
            if sinal == "(-)":
                valor= valor.replace(".", "")
                linha_formatada = f"{data}; {historico}; {lote} {documento}; ; {valor}\n"
            else:
                valor= valor.replace(".", "")
                linha_formatada = f"{data}; {historico}; {lote} {documento}; {valor};\n"
            linhas_processadas.append(linha_formatada)
            continue  # Pular para a próxima linha se o primeiro padrão corresponder

        # Teste para o segundo padrão
        correspondencia2 = padrao2.match(linha)
        if correspondencia2:
            valor, sinal, data, historico = correspondencia2.groups()
            # Remover acentos do histórico
            historico = remover_acentos(historico)
            
            if sinal == "(-)":
                valor= valor.replace(".", "")
                linha_formatada = f"{data}; {historico};;;{valor};\n"
            else:
                valor= valor.replace(".", "")
                linha_formatada = f"{data}; {historico};;{valor};\n"
            linhas_processadas.append(linha_formatada)

    # Retorna o cabeçalho seguido pelas linhas processadas
    return cabecalho + ''.join(linhas_processadas)

