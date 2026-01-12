import os
from interfaz import *
from persistencia import *
from gestorTiempos import *

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
                etapa = int(input("Etapa: "))
                tiempo = input("Tiempo: ")
                tiempo_milis = tiempo_a_milisegundos(tiempo)
                add_time(competicion_escogida, tiempo_milis, etapa, participante)
                os.system("cls")
                mostrarDatos(competicion_escogida)
            if b == 3:
                etapa = int(input("Etapa: "))
                fill_times(competicion_escogida, etapa)
                os.system("cls")
                mostrarDatos(competicion_escogida)
            if b == 4:
                participante = input("Participante: ")
                etapa = int(input("Etapa: "))
                fill_times_penalitation(competicion_escogida, etapa, participante)
                os.system("cls")
                mostrarDatos(competicion_escogida)

    if a == 2:
        nombre = input("Ingrese el nombre de la competicion: ")

        numParticipantes = int(input("Ingrese numero de participantes: "))
        participantes = []
        for i in range(numParticipantes):
            nombreParticipante = input(f"Ingrese el nombre del participante {i+1}: ")
            participantes.append(nombreParticipante)

        numEtapas = int(input("Ingrese el numero de etapas: "))

        add_competition(nombre, numEtapas, participantes)

    if a == 3:
        cargarCompeticiones()
        nombre = input("Ingrese el nombre de la competicion: ")
        delete_competition(nombre)


# CREATE TABLE times (competition_id int, time int, numberOfStage int, participant varchar2(255), foreign key(competition_id) references competitions(id))
