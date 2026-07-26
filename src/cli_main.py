import os
from interfaz import *
from servicios import RallyService


service = RallyService()


def leer_entero(mensaje):
    valor = input(mensaje)
    try:
        return int(valor)
    except ValueError:
        return valor


def mostrar_resultado(mensaje):
    input(f"{mensaje}\nPulse Enter para continuar...")

finalizarPrograma = False
while finalizarPrograma == False:
    os.system("cls")
    menuPrincipal()
    a = int(input())
    if a == 0:
        finalizarPrograma = True

    if a == 1:
        cargarCompeticiones()
        competicion_escogida = input("Escoja competicion: ")
        finalizarMenu = False
        os.system("cls")
        while finalizarMenu == False:
            menuCompeticion()
            b = int(input())

            if b == 0:
                finalizarMenu = True

            if b == 1:
                os.system("cls")
                mostrarDatos(competicion_escogida)

            if b == 2:
                participante = input("Participante: ")
                etapa = leer_entero("Etapa: ")
                tiempo = input("Tiempo: ")
                _ok, mensaje = service.add_time_str(
                    competicion_escogida, participante, etapa, tiempo
                )
                os.system("cls")
                print(mensaje)
                mostrarDatos(competicion_escogida)
            if b == 3:
                etapa = leer_entero("Etapa: ")
                _ok, mensaje = service.fill_missing_times(competicion_escogida, etapa)
                os.system("cls")
                print(mensaje)
                mostrarDatos(competicion_escogida)
            if b == 4:
                participante = input("Participante: ")
                etapa = leer_entero("Etapa: ")
                segundos = input("Segundos de penalizacion: ")
                _ok, mensaje = service.penalize(
                    competicion_escogida, etapa, participante, segundos
                )
                os.system("cls")
                print(mensaje)
                mostrarDatos(competicion_escogida)

    if a == 2:
        nombre = input("Ingrese el nombre de la competicion: ")

        numParticipantes = leer_entero("Ingrese numero de participantes: ")
        if not isinstance(numParticipantes, int) or numParticipantes <= 0:
            mostrar_resultado("El numero de participantes debe ser un entero mayor que cero.")
            continue
        participantes = []
        for i in range(numParticipantes):
            nombreParticipante = input(f"Ingrese el nombre del participante {i+1}: ")
            participantes.append(nombreParticipante)

        numEtapas = leer_entero("Ingrese el numero de etapas: ")

        _ok, mensaje = service.create_competition(nombre, numEtapas, participantes)
        mostrar_resultado(mensaje)

    if a == 3:
        cargarCompeticiones()
        nombre = input("Ingrese el nombre de la competicion: ")
        _ok, mensaje = service.delete_competition(nombre)
        mostrar_resultado(mensaje)


# CREATE TABLE times (competition_id int, time int, numberOfStage int, participant varchar2(255), foreign key(competition_id) references competitions(id))
