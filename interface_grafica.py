import sys
from PyQt5 import QtWidgets

class InterfaceGrafica(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Extrato')
        
        self.layout = QtWidgets.QVBoxLayout()
        
        self.mes_label = QtWidgets.QLabel('Informe o mês (mm):')
        self.mes_input = QtWidgets.QLineEdit(self)
        
        self.ano_label = QtWidgets.QLabel('Informe o ano (aaaa):')
        self.ano_input = QtWidgets.QLineEdit(self)
        
        self.conta_banco_label = QtWidgets.QLabel('Informe o número da conta do banco:')
        self.conta_banco_input = QtWidgets.QLineEdit(self)
        
        self.saldo_inicial_label = QtWidgets.QLabel('Informe o saldo inicial:')
        self.saldo_inicial_input = QtWidgets.QLineEdit(self)
        
        self.ok_button = QtWidgets.QPushButton('OK', self)
        self.ok_button.clicked.connect(self.accept)
        
        self.layout.addWidget(self.mes_label)
        self.layout.addWidget(self.mes_input)
        self.layout.addWidget(self.ano_label)
        self.layout.addWidget(self.ano_input)
        self.layout.addWidget(self.conta_banco_label)
        self.layout.addWidget(self.conta_banco_input)
        self.layout.addWidget(self.saldo_inicial_label)
        self.layout.addWidget(self.saldo_inicial_input)
        self.layout.addWidget(self.ok_button)
        
        self.setLayout(self.layout)

def get_user_input_and_cabecalho():
    dialog = InterfaceGrafica()
    
    if dialog.exec_() == QtWidgets.QDialog.Accepted:
        mes = dialog.mes_input.text()
        ano = dialog.ano_input.text()
        conta_banco = dialog.conta_banco_input.text()
        saldo_inicial = dialog.saldo_inicial_input.text()
        
        if not all([mes, ano, conta_banco, saldo_inicial]):
            QtWidgets.QMessageBox.information(None, "Erro", "Preencha os campos corretamente")
            sys.exit(1)
        else:
            cabecalho = f"Cabeçalho;;;;;\nCompetencia;01/{mes}/{ano};Conta Banco;{conta_banco};Saldo Inicial;{saldo_inicial}\nLançamentos;;;;;\n"
            
            pdf_path = QtWidgets.QFileDialog.getOpenFileName(None, "Selecione o arquivo PDF", "", "PDF files (*.pdf)")[0]
            output_txt_path = QtWidgets.QFileDialog.getSaveFileName(None, "Salvar arquivo de saída como", "", "Text files (*.txt)")[0]
            
            return mes, ano, conta_banco, saldo_inicial, cabecalho, pdf_path, output_txt_path
    else:
        sys.exit(1)
