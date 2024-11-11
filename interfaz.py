import os
from persistencia import *
from gestorTiempos import * 
def menuPrincipal():
    print("---------------------------\n      Menú principal     \n      --------------      ")
    print("  -> Pulse 1 para cargar competicion")
    print("  -> Pulse 2 para crear competicion")
    print("  -> Pulse 3 para borrar competicion")
    print("  -> Pulse 0 para cerrar el programa")

def cargarCompeticiones():
    
    competiciones = get_competitions()
    os.system('cls')
    print("---------------------------\n      Competiciones     \n      --------------      ")
    
    for competicion in competiciones:
        print("  -", competicion[0])
    

def menuCompeticion():
    print("---------------------------\n      Menú competicion     \n      --------------      ")
    print("  -> Pulse 1 para mostrar datos")
    print("  -> Pulse 2 para añadir tiempo")
    print("  -> Pulse 3 para rellenar abandonos")
    print("  -> Pulse 4 para rellenar descalificaciones")
    print("  -> Pulse 0 para volver al menú principal")
    
    
def mostrarDatos(competicion_escogida):
    competition = get_competition(competicion_escogida)
    print("\t\t",end='')
    for i in range(1, competition[2]+1):
        print("Tramo "+str(i)+"           ",end='')
    print("General")
    
    participantes =  orderParticipants(get_participants(competition[0]), competition[0])
    
    i = 1
    mejor_tiempo = 0
    for participante, tiempo_total in participantes:
        if len(participante) < 5:
            print(str(i)+"- "+participante+"\t\t:",end='')    
        else :
            print(str(i)+"- "+participante+"\t:",end='')
        
        tiempos = get_times(participante, competition[0])
        
        for j in range(competition[2]):
            try:
                tiempo = tiempos[j][0]
                print(milisegundos_a_tiempo(tiempo)+"       || ",end='')
            except IndexError:
                print(milisegundos_a_tiempo(0)+"       || ",end='')
        
        if i == 1:
            print(milisegundos_a_tiempo(tiempo_total))
            mejor_tiempo = tiempo_total
        else:
            print(milisegundos_a_tiempo(tiempo_total)+"  +"+milisegundos_a_tiempo(tiempo_total-mejor_tiempo))
        
        i += 1
            
        
        
    