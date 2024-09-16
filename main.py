import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel

# Crear una clase para la ventana principal
class MiVentana(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
    
    def initUI(self):
        # Configurar la ventana
        self.setGeometry(100, 100, 300, 200)
        self.setWindowTitle('Mi primera aplicación PyQt')

        # Crear una etiqueta
        label = QLabel('¡Hola, PyQt!', self)
        label.move(100, 80)  # Posicionar la etiqueta

# Punto de entrada de la aplicación
if __name__ == '__main__':
    app = QApplication(sys.argv)
    ventana = MiVentana()
    ventana.show()
    sys.exit(app.exec_())