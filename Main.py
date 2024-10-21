import sys
import mysql.connector
from mysql.connector import Error
from PyQt5 import QtWidgets
import config  

#modulos
from interface_grafica import get_user_input_and_cabecalho
from Bancos import extract_sicoob,extract_sicredi,extract_caixa,extract_bradesco,extract_cseis


class Conexao_DataBase:
    def __init__(self):
        self.connection = self.criando_conexao()
    
    def criando_conexao(self):
        connection = None
        try:
            connection = mysql.connector.connect(
                host=config.DB_host,
                user=config.DB_user,
                password=config.DB_passwd,
                database=config.DB_database,
                auth_plugin='mysql_native_password'  # Adiciona a especificação do plugin de autenticação
            )
            print("Conexão com o banco de dados MySQL bem-sucedida")
        except Error as e:
            print(f"Ocorreu o erro '{e}'")
        
        return connection
    
    def fechando_conexao(self):
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("Conexão com o banco de dados MySQL encerrada")

    def fetch_data(self, query, params=None):
        cursor = self.connection.cursor(dictionary=True)
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            results = cursor.fetchall()
            return results
        except Error as e:
            print(f"Ocorreu o erro '{e}' ao executar a consulta")
            return None
        finally:
            cursor.close()

class Solicitacao(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Banco')
        
        self.layout = QtWidgets.QVBoxLayout()
        
        self.banco_label = QtWidgets.QLabel('Informe o banco')
        self.banco_input = QtWidgets.QLineEdit(self) 
        
        self.pesquisar_button = QtWidgets.QPushButton('Pesquisar', self)
        self.pesquisar_button.clicked.connect(self.accept)
        
        self.layout.addWidget(self.banco_label)
        self.layout.addWidget(self.banco_input)
        self.layout.addWidget(self.pesquisar_button)
        
        self.setLayout(self.layout)

def process_pdf(banco_nome):
    mes, ano, conta_banco, saldo_inicial, cabecalho, pdf_path, output_txt_path = get_user_input_and_cabecalho()
    processing_functions = {
        "SICOOB": extract_sicoob,
        "SICREDI": extract_sicredi,
        "CAIXA": extract_caixa,
        "BRADESCO": extract_bradesco,
        "C6": extract_cseis
    }
    if banco_nome in processing_functions:
        if banco_nome == 'BRADESCO':
            processing_functions[banco_nome](pdf_path, output_txt_path, cabecalho, mes, ano)
        else:
            processing_functions[banco_nome](pdf_path, output_txt_path, cabecalho)
        QtWidgets.QMessageBox.information(None, "Sucesso", "Arquivos salvos com sucesso!")
    else:
        QtWidgets.QMessageBox.information(None, "Erro", f"Processamento para o banco {banco_nome} não está disponível")

def main():
    conexao = Conexao_DataBase()
    app = QtWidgets.QApplication(sys.argv)
    dialogo = Solicitacao()
    
    if dialogo.exec_() == QtWidgets.QDialog.Accepted:
        banco = dialogo.banco_input.text().strip().upper()
        if not banco:
            QtWidgets.QMessageBox.information(None, "Erro", "Preencha os campos corretamente")
            sys.exit(1)
        else:
            query = "SELECT Nome_Banco FROM banco WHERE Nome_Banco = %s"
            results = conexao.fetch_data(query, (banco,))
            
            if results:
                for row in results:
                    banco_nome = row['Nome_Banco'].upper()
                    process_pdf(banco_nome)
            else:
                QtWidgets.QMessageBox.information(None, "Erro", "Nenhum dado encontrado ou erro na consulta")
        
        conexao.fechando_conexao()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
