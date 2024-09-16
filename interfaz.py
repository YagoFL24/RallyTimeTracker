from persistencia import *
def menuPrincipal():
    print("---------------------------\n      Menú principal     \n      --------------      ")
    print("  -> Pulse 1 para cargar competicion")
    print("  -> Pulse 2 para crear competicion")
    print("  -> Pulse 0 para cerrar el programa")

def crearCompeticion():
    nombre = input("Ingrese el nombre de la competicion: ")


    numParticipantes = input("Ingrese numero de participantes: ")
    participantes = []
    for i in range(numParticipantes):
        nombreParticipante = input(f"Ingrese el nombre del participante {i+1}: ")
        participantes.append(nombreParticipante)

    numEtapas = input("Ingrese el numero de etapas: ")

    add_competition(nombre, numEtapas, participantes)

    print(f"Competicion '{nombre}' creada exitosamente.")


def cargarCompeticion():
    competiciones = cargarCompeticiones()

def menuCompeticion():
    print("---------------------------\n      Menú principal     \n      --------------      ")
    print("  -> Pulse 1 para cargar competicion")
    print("  -> Pulse 2 para crear competicion")
    print("  -> Pulse 0 para cerrar el programa")