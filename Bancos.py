#importações
import re
import pytesseract
import pdfplumber
import sys
import os
import fitz  # Importa PyMuPDF
import unicodedata
import cv2
import numpy as np
from PIL import Image
from pdf2image import convert_from_path
from PyPDF2 import PdfReader
from PyQt5 import QtWidgets


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


def extract_bradesco(pdf_path, output_txt_path, cabecalho, mes, ano):
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

def extract_sicoob(pdf_path, output_txt_path, cabecalho):
    print("sicoob")
    reader = PdfReader(pdf_path)
    extracted_text = [page.extract_text() for page in reader.pages]

    pattern = r'(\d{2}/\d{2}/\d{4})\s*(\S*)?\s*([\wáéíóúÁÉÍÓÚàèìòùÀÈÌÒÙäëïöüÄËÏÖÜãñõÃÑÕçÇ\s/\-.]+)\s+(\d{1,3}(?:\.\d{3})*,\d{2}[DC])'

    entries = []

    for page_text in extracted_text:
        matches = re.findall(pattern, page_text, re.DOTALL)
        entries.extend(matches)

    formatted_txt_lines = ['Data;Historico;Documento;Valor Credito (Subtrai);Valor Debito (Soma);\n']

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
        text_file.write(cabecalho)
        text_file.writelines(formatted_txt_lines)


'''------------------------------------------------------------------------------------------------------------'''

'''SICREDI PDF'''


def debito(description):
    debit_keywords = ["PAGAMENTO PIX", "PAG DEB", "SAQUE", "TARIFA", "COMPRA", "IOF ADICIONAL", "IOF BASICO"," LIQUIDACAO DE PARCELA","CHEQUE COMPE","CESTA DE RELACIONAMENTO", "CH.PAGO", "TARIFA SERV","DEB.CTA.FATURA", "DEBITO CONVENIOS","IOF S/ OPER","JUROS UTILIZ.CH.ESPECIAL","APLIC.FINANC.AVISO PREVIO", "INTEGR.CAPITAL",
                      "CH.PAGO", "IOF","LIQUIDACAO", "DEB.","CHEQUE A PARTIR", "SEGURO","DEBITO ARRECADACAO", "DEBITO CHEQUE", 'TRANSF ENTRE CONTAS','APLICACAO FINANCEIRA','FOLHA CHEQUE ','MANUTENCAO DE TITULOS','AMORTIZACAO CONTRATO','JUROS ADTO. CREDITO ','ADIANT. DEPOSITANTE','DEPOSITANTE','JUROS CHEQUE INADIMPLENTE',
                      'DEV. CHEQUE DEPOSITADO','CUSTAS DE PROTESTO','CHQ.APRESENTADO CX.','SUSTACAO/REVOGACAO','CHEQUE DEVOLVIDO','APLICACAO','PAGTO JUROS CONTR ROTATIV']
    if "estorno" in description.lower():
        for keyword in debit_keywords:
            if "estorno " + keyword.lower() in description.lower():
                return False
    return any(keyword in description for keyword in debit_keywords)

def credito(description):
    credit_keywords = ["TED ",#"DEP CHEQUE",
                       "ESTORNO"," RECEBIMENTO PIX","LIQ.COBRANCA SIMPLES","DEP CHEQUE 24H CANAIS","DEPOSITO CX ELETRONICO" ]
    return any(keyword in description for keyword in credit_keywords)

def extract_sicredi(pdf_path, output_txt_path, cabecalho):
    print("sicredi")
    reader = PdfReader(pdf_path)
    extracted_text = [page.extract_text() for page in reader.pages]

    pattern = r'(\d{2}/\d{2}/\d{4})\s+([\w\d\S\s]{9})\s{2}([\w\s\S]{50})\s+(\d{1,3}(?:\.\d{3})*,\d{2})'
    entries = []

    for page_text in extracted_text:
        matches = re.findall(pattern, page_text, re.DOTALL)
        entries.extend(matches)

    formatted_txt_lines = ['Data;Historico;Documento;Valor Credito (Subtrai);Valor Debito (Soma);\n']

    for entry in entries:
        date, code, description, value = entry
        amount = value.replace('.', '')

        if credito(description):
            line = f"{date};{description};{code};{amount};;\n"
        elif debito(description):
            line = f"{date};{description};{code};;{amount};\n"
        else:
            line = f"{date};{description};{code};{amount};;\n"

        formatted_txt_lines.append(line)

    with open(output_txt_path, 'w', encoding='utf-8') as text_file:
        text_file.write(cabecalho)
        text_file.writelines(formatted_txt_lines)

