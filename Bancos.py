import re
import pytesseract
import pdfplumber
import sys
import os
import io
import fitz  # Importa PyMuPDF
import unicodedata
import cv2
import numpy as np
from PIL import Image
from pdf2image import convert_from_path
from PyPDF2 import PdfReader
from PyQt5 import QtWidgets


'''------------------------------------------------------------------------------------------------------------'''

'''BANCO DO BRASIL'''

def extract_banco_do_brasil(pdf_path, output_txt_path, cabecalho):
    print("Processando extrato do Banco do Brasil")
    
    try:
        # Leitura do PDF
        with open(pdf_path, 'rb') as pdf_file:
            pdf_reader = PdfReader(pdf_file)
            all_text = "".join(page.extract_text() or '' for page in pdf_reader.pages)

        lines = all_text.split('\n')
        
        # Padrões de regex para tentar
        padrao1 = re.compile(r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*(\(-\)|\(\+\))\s*(\d{2}/\d{2}/\d{4})\s*(\d+)\s*(\d+)\s*(.*)")
        padrao2 = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2})\s*(\(-\)|\(\+\))\s*(\d{2}/\d{2}/\d{4})\s*(.*)")

        linhas_processadas = []

        for linha in lines:
            if "Saldo Anterior" in linha or "S A L D O" in linha:
                continue
            # Teste para o primeiro padrão
            correspondencia1 = padrao1.match(linha)
            if correspondencia1:
                valor, sinal, data, lote, documento, historico = correspondencia1.groups()
                if sinal == "(-)":
                    linha_formatada = f"{data}; {historico}; {lote} {documento}; {valor};\n"
                else:
                    linha_formatada = f"{data}; {historico}; {lote} {documento}; ; {valor};\n"
                linhas_processadas.append(linha_formatada)
                continue  # Pular para a próxima linha se o primeiro padrão corresponder

            # Teste para o segundo padrão
            correspondencia2 = padrao2.match(linha)
            if correspondencia2:
                valor, sinal, data, historico = correspondencia2.groups()
                if sinal == "(-)":
                    linha_formatada = f"{data}; {historico};;{valor};\n"
                else:
                    linha_formatada = f"{data}; {historico};;;{valor}\n"
                linhas_processadas.append(linha_formatada)

        # Escrevendo no arquivo de saída
        with open(output_txt_path, 'w', encoding='utf-8') as arquivo_saida:
            arquivo_saida.write(cabecalho + "\n")  # Cabeçalho
            for linha in linhas_processadas:
                arquivo_saida.write(linha)

        print(f"Arquivo TXT criado com sucesso: {output_txt_path}")
        print(f"Número de linhas escritas: {len(linhas_processadas)}")

    except FileNotFoundError:
        print(f"Erro: O arquivo PDF não foi encontrado: {pdf_path}")
    except PermissionError:
        print(f"Erro: Sem permissão para acessar o arquivo: {pdf_path}")
    except Exception as e:
        print(f"Ocorreu um erro: {str(e)}")


'''------------------------------------------------------------------------------------------------------------'''

'''BRADESCO PDF'''

def extract_bradesco_PDF(pdf_path, output_txt_path, cabecalho, mes, ano):
    print("Processando extrato do Bradesco (PDF)")
    
    try:
        # Criando um objeto PdfReader
        pdf_reader = PdfReader(pdf_path)
        
        # Abrindo o arquivo txt para escrita
        with open(output_txt_path, 'w', encoding='utf-8') as txt_file:
            txt_file.write(cabecalho + "\n")  # Escreve o cabeçalho primeiro
            last_date = ""  # Variável para armazenar a última data encontrada
            line_group = ""  # Armazena o grupo de linhas a ser concatenado
            
            # Iterando sobre todas as páginas do PDF
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                
                # Removendo informações desnecessárias logo após a extração do texto
                text = re.sub(r'(Folha .*|CNPJ: .*|Nome do usuário: .*|Data da operação: .*|(?<! )Folha .*|(?<! )CNPJ: .*|(?<! )Nome do usuário: .*|(?<! )Data da operação: .*)', '', text)
                
                lines = text.splitlines()
                
                for line in lines:
                    date_match = re.match(r'(\d{2}/\d{2}/\d{4})', line)
                    ends_with_value = re.search(r'-?\d{1,3}(?:\.\d{3})*(?:,\d{2})$', line)
                    
                    if date_match:
                        if line_group and re.search(r'-?\d{1,3}(?:\.\d{3})*(?:,\d{2})$', line_group.strip()):
                            line_group = line_group.strip()
                            txt_file.write(f"{last_date}; {line_group.strip()}\n")
                        
                        last_date = date_match.group(1)
                        line_group = line[len(date_match.group(0)):].strip()
                        
                    elif ends_with_value:
                        line_group += f"; {line}"
                        if re.search(r'-?\d{1,3}(?:\.\d{3})*(?:,\d{2})$', line_group.strip()):
                            line_group = line_group.strip()
                            if line_group.startswith('; '):
                                line_group = line_group[2:]
                            txt_file.write(f"{last_date}; {line_group.strip()}\n")
                        line_group = ""
                    else:
                        line_group += f" {line}"

                if line_group and re.search(r'-?\d{1,3}(?:\.\d{3})*(?:,\d{2})$', line_group.strip()):
                    line_group = line_group.strip()
                    if line_group.startswith('; '):
                        line_group = line_group[2:]
                    txt_file.write(f"{last_date}; {line_group.strip()}\n")
                    line_group = ""

        # Remover o último valor das linhas e filtrar por mês/ano
        with open(output_txt_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        
        with open(output_txt_path, 'w', encoding='utf-8') as file:
            file.write(cabecalho + "\n")  # Reescreve o cabeçalho
            for line in lines:
                if re.match(r'^\d{2}/\d{2}/\d{4}', line):
                    # Verificar mês e ano
                    data_match = re.match(r'(\d{2})/(\d{2})/(\d{4})', line)
                    if data_match:
                        mes_linha = data_match.group(2)
                        ano_linha = data_match.group(3)
                        
                        if mes_linha != mes or ano_linha != ano:
                            continue  # Pula para próxima linha se não for do mês/ano desejado
                    
                    modified_line = re.sub(r'(-?\d{1,3}(?:\.\d{3})*(?:,\d{2}))\s*$', '', line.strip())
                    remaining_values = re.search(r'(-?\d{1,3}(?:\.\d{3})*(?:,\d{2}))\s*$', modified_line)
                    
                    if remaining_values:
                        valor = remaining_values.group(0).strip()
                        modified_line = modified_line[:modified_line.rfind(valor)].strip()
                    else:
                        valor = ""
                    
                    parts = modified_line.split(';')
                    if len(parts) >= 2:
                        data = parts[0].strip()
                        historico = ' '.join(parts[1:]).strip()
                        historico = re.sub(r'Extrato Mensal / Por Período AMARAL, MOREIRA & AMARAL OTICA LTDA \|    ', '', historico)

                        if "Total" not in historico and historico:
                            if valor:
                                valor = valor.replace('.', '')  # Remove os pontos do valor
                                if '-' in valor:  # Verifica se é um valor negativo
                                    valor = valor.replace('-', '')  # Remove o sinal negativo
                                    file.write(f"{data};{historico};;;{valor};\n")  # Valor negativo vai para a coluna de débito
                                else:
                                    file.write(f"{data};{historico};;{valor};;\n")  # Valor positivo vai para a coluna de crédito

        print(f"Arquivo TXT criado com sucesso: {output_txt_path}")
        return True

    except Exception as e:
        print(f"Ocorreu um erro: {str(e)}")
        return False

'''------------------------------------------------------------------------------------------------------------'''

'''BRADESCO OCR'''


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


def extract_bradesco_OCR(pdf_path, output_txt_path, cabecalho, mes, ano):
    print("Processando extrato do Bradesco")
    
    images = convert_from_path(pdf_path)
    
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
    
    with open(output_txt_path, 'w', encoding='utf-8') as f:
        f.write(cabecalho + "\n")
        for line in processed_lines:
            f.write(line + "\n")
    
    error_path = os.path.join(os.path.dirname(output_txt_path), "erro.txt")
    with open(error_path, 'w', encoding='utf-8') as f:
        f.write("Linhas ignoradas:\n")
        for line in ignored_lines:
            f.write(line + "\n")
    
    app = QtWidgets.QApplication(sys.argv)
    QtWidgets.QMessageBox.information(None, "Sucesso", "Arquivos salvos com sucesso!")
    sys.exit(app.exec_())

'''------------------------------------------------------------------------------------------------------------'''

'''CAIXA'''


def extract_caixa(pdf_path, output_path, cabecalho):
    print("caixa")
    date_pattern = re.compile(r"^\s*\d{2}/\d{2}/\d{4}")
    exclude_phrase = "SALDO DIA"
    data_pattern = re.compile(r"(\d{2}/\d{2}/\d{4})\s+(\d{6})\s+(.+?)\s+([\d.,]+)\s+([CD])")

    with fitz.open(pdf_path) as doc:
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
    
    with open(output_path, 'w', encoding='utf-8') as output_file:
        output_file.write('\n'.join(formatted_lines))


'''------------------------------------------------------------------------------------------------------------'''

'''C6 PDF'''


def extract_cseis(pdf_path, output_txt_path, cabecalho):
    print("c6")
    date_pattern = re.compile(r'^(\d{2}/\d{2}/\d{4})')
    historico_pattern = re.compile(r'(.+?)(?=\w+?\d{11}\s)')
    doc_pattern = re.compile(r'(\d{11})')
    valor_pattern = re.compile(r'(\d{1,3}(?:\.\d{3})*,\d{2})\s([DC])')
    
    with pdfplumber.open(pdf_path) as pdf, open(output_txt_path, 'w', encoding='utf-8') as output_file:
        output_file.write(cabecalho)      
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
                        
                        output_file.write(f"{date_match.group(1)};{historico_match.group(0)};{doc_match.group(1)};")
                        if valor_match.group(2) == 'D':
                            output_file.write(f";{valor_formatado};")
                        else:
                            output_file.write(f"{valor_formatado};;")
                            
                        output_file.write("\n")


'''------------------------------------------------------------------------------------------------------------'''

'''SICOOB PDF'''


def remover_acentos(texto):
    texto_normalizado = unicodedata.normalize('NFD', texto)
    return re.sub(r'[\u0300-\u036f]', '', texto_normalizado)

def is_debit(value_indicator):
    return value_indicator == 'D'

def sicoob_banco(pdf_path, output_txt_path, cabecalho):
    print("extrato enviado pelo banco?")
    reader = PdfReader(pdf_path)
    extracted_text = [page.extract_text() for page in reader.pages]

    pattern = r'(\d{2}/\d{2}/\d{4})\s*(\S*)?\s*([\wáéíóúÁÉÍÓÚàèìòùÀÈÌÒÙäëïöüÄËÏÖÜãñõÃÑÕçÇ\s/\-.]+)\s+(\d{1,3}(?:\.\d{3})*,\d{2}[DC])'

    entries = []

    for page_text in extracted_text:
        matches = re.findall(pattern, page_text, re.DOTALL)
        entries.extend(matches)

    formatted_txt_lines = [
        'Cabeçalho;;;;;\n',
        'Competencia;01/10/2024;Conta Banco;1;Saldo Inicial;1\n',
        'Lançamentos;;;;;\n',
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

    with open(output_txt_path, 'w', encoding='utf-8') as text_file:
        text_file.writelines(formatted_txt_lines)

    return len(formatted_txt_lines)

def sicoob_cliente(pdf_path, output_txt_path, cabecalho,ano):
    print("extrato enviado pelo cliente")
    # Abre o arquivo PDF
    with open(pdf_path, 'rb') as arquivo_pdf:
        # Cria um leitor de PDF
        leitor_pdf = PdfReader(arquivo_pdf)
        
        # Abre o arquivo TXT para escrita
        with open(output_txt_path, 'w', encoding='utf-8') as arquivo_txt:
            # Escreve o cabeçalho
            arquivo_txt.write('Cabeçalho;;;;;\n')
            arquivo_txt.write('Competencia;01/10/2024;Conta Banco;1;Saldo Inicial;1\n')
            arquivo_txt.write('Lançamentos;;;;;\n')
            arquivo_txt.write('Data;Historico;Documento;Valor Credito (Subtrai);Valor Debito (Soma);\n')
            
            # Itera sobre cada página do PDF
            for pagina in range(len(leitor_pdf.pages)):
                # Extrai o texto da página
                texto = leitor_pdf.pages[pagina].extract_text()
                
                # Usa expressão regular para separar linhas com datas
                linhas = re.split(r'(?=\d{2}/\d{2})', texto)
                
                # Processa cada linha
                for linha in linhas:
                    linha = linha.strip()  # Remove espaços em branco no início e fim
                    # Verifica se a linha começa com uma data
                    if linha and re.match(r'\d{2}/\d{2}', linha):
                        # Separa os componentes da linha
                        componentes = re.match(r'(\d{2}/\d{2})(.+?)(\d{1,3}(?:\.\d{3})*,\d{2}[CD])(.+)', linha)
                        if componentes:
                            data = componentes.group(1)
                            historico = componentes.group(2)
                            valor = componentes.group(3)
                            documento = componentes.group(4)
                            
                            # Ajusta o histórico e o valor se necessário
                            match_valor = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2}[CD])$', historico + valor)
                            if match_valor:
                                valor_completo = match_valor.group(1)
                                historico = (historico + valor)[:-(len(valor_completo))]
                                valor = valor_completo.replace(".", "")
                            
                            # Verifica se o histórico contém "SALDO DO DIA"
                            if "SALDO DO DIA" not in historico.upper():
                                # Verifica se o valor é crédito (C) ou débito (D)
                                if valor.endswith('C'):
                                    linha_formatada = f"{data.strip()}/{ano};{historico.strip()};{documento.strip()};{valor.strip()[:-1]};;\n"
                                elif valor.endswith('D'):
                                    linha_formatada = f"{data.strip()}/{ano};{historico.strip()};{documento.strip()};;{valor.strip()[:-1]};\n"
                                else:
                                    # Caso não seja identificado C ou D, mantém o formato original
                                    linha_formatada = f"linha não sem valor:\n{data.strip()}/{ano};{historico.strip()};{documento.strip()};{valor.strip()}\n"
                                
                                arquivo_txt.write(linha_formatada)

def extract_sicoob(caminho_pdf, caminho_txt, cabecalho, ano):
    # Tenta primeiro com extract_sicoob
    linhas_sicoob = sicoob_banco(caminho_pdf, caminho_txt, cabecalho)
    
    # Se extract_sicoob produziu 4 ou menos linhas, usa pdf_para_txt
    if linhas_sicoob <= 4:
        sicoob_cliente(caminho_pdf, caminho_txt, cabecalho,ano)
    else:
        print(f"Extraído com sucesso usando extract_sicoob. Linhas processadas: {linhas_sicoob}")


'''------------------------------------------------------------------------------------------------------------'''

'''SICREDI PDF'''

def extract_sicredi(pdf_path, output_txt_path, cabecalho):
    try:
        # Abre o arquivo PDF e extrai o texto
        with open(pdf_path, 'rb') as arquivo_pdf:
            leitor_pdf =PdfReader(arquivo_pdf)
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
                transacao_formatada = f"{data} ; {historico} ; {codigo} ; {debito} ; {credito} ; ;"
                transacoes_formatadas.append(transacao_formatada)

        # Salvar as transações formatadas em um arquivo TXT
        with open(output_txt_path, 'w', encoding='utf-8') as arquivo_txt:
            arquivo_txt.write(cabecalho)
            for transacao in transacoes_formatadas:
                arquivo_txt.write(transacao + '\n')
        print(f"Transações salvas em {output_txt_path}.")

    except FileNotFoundError:
        print(f"Erro: O arquivo PDF '{pdf_path}' não foi encontrado.")
    except Exception as e:
        print(f"Ocorreu um erro: {e}")

