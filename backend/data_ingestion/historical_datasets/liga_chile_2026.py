# -*- coding: utf-8 -*-
"""Liga de Primera 2026 (Chile) - Fechas 1 a 21.
Fuente: T13 / Deportes13 (fixture oficial con resultados), consultado 05-09-2026.
(jornada, fecha, hora, estadio, local, gl, gv, visita, estado, obs)
"""

UCH = "Universidad de Chile"
UC = "Universidad Catolica"
UDEC = "Universidad de Concepcion"
CC = "Colo-Colo"
COQ = "Coquimbo Unido"
LSE = "Deportes La Serena"
LIM = "Deportes Limache"
DCO = "Deportes Concepcion"
ULC = "Union La Calera"
AUD = "Audax Italiano"
PAL = "Palestino"
COB = "Cobresal"
HUA = "Huachipato"
NUB = "Nublense"
EVE = "Everton"
OHI = "O'Higgins"

EQUIPOS = [UCH, UC, UDEC, CC, COQ, LSE, LIM, DCO, ULC, AUD, PAL, COB, HUA, NUB, EVE, OHI]

J = "Jugado"
S = "Suspendido"

PARTIDOS = [
    (1, "30/01/2026", "20:00", "Estadio Nacional", UCH, 0, 0, AUD, J, ""),
    (1, "31/01/2026", "12:00", "Elias Figueroa", LIM, 3, 1, CC, J, ""),
    (1, "31/01/2026", "15:30", "Ester Roa", UDEC, 1, 0, COQ, J, ""),
    (1, "31/01/2026", "18:00", "El Cobre", COB, 1, 0, HUA, J, ""),
    (1, "01/02/2026", "18:00", "La Portada", LSE, 2, 2, UC, J, ""),
    (1, "01/02/2026", "20:30", "La Cisterna", PAL, 1, 1, NUB, J, ""),
    (1, "02/02/2026", "18:00", "Sausalito", EVE, 0, 1, ULC, J, ""),
    (1, "02/02/2026", "20:30", "Ester Roa", DCO, 2, 1, OHI, J, ""),

    (2, "06/02/2026", "20:00", "La Florida", AUD, 3, 0, UDEC, J, ""),
    (2, "07/02/2026", "12:00", "Sanchez Rumoroso", COQ, 3, 1, PAL, J, ""),
    (2, "07/02/2026", "18:00", "El Teniente", OHI, 1, 0, LSE, J, ""),
    (2, "07/02/2026", "20:30", "Monumental", CC, 2, 0, EVE, J, ""),
    (2, "08/02/2026", "12:00", "Huachipato CAP Acero", HUA, 2, 1, UCH, J, ""),
    (2, "08/02/2026", "18:00", "Nelson Oyarzun", NUB, 1, 1, LIM, J, ""),
    (2, "08/02/2026", "20:30", "Claro Arena", UC, 2, 0, DCO, J, ""),
    (2, "09/02/2026", "20:00", "Nicolas Chahuan", ULC, 3, 1, COB, J, ""),

    (3, "13/02/2026", "18:00", "Sausalito", EVE, 0, 3, HUA, J, "Fuente indica 'Nicolas Chahuan'; se corrige a Sausalito (localia de Everton)"),
    (3, "13/02/2026", "20:30", "La Cisterna", PAL, 0, 0, UCH, J, ""),
    (3, "14/02/2026", "12:00", "La Portada", LSE, 0, 1, COQ, J, ""),
    (3, "14/02/2026", "18:00", "Lucio Farina", LIM, 2, 1, OHI, J, ""),
    (3, "14/02/2026", "20:30", "El Cobre", COB, 3, 2, UC, J, ""),
    (3, "15/02/2026", "12:00", "Ester Roa", UDEC, 2, 1, DCO, J, ""),
    (3, "15/02/2026", "18:00", "Nelson Oyarzun", NUB, 1, 0, AUD, J, ""),
    (3, "15/02/2026", "20:30", "Monumental", CC, 1, 0, ULC, J, ""),

    (4, "20/02/2026", "18:00", "Nicolas Chahuan", ULC, 0, 1, NUB, J, ""),
    (4, "20/02/2026", "20:30", "Ester Roa", DCO, 1, 1, COB, J, ""),
    (4, "21/02/2026", "12:00", "Huachipato CAP Acero", HUA, 2, 1, PAL, J, ""),
    (4, "21/02/2026", "18:00", "El Teniente", OHI, 0, 1, CC, J, ""),
    (4, "21/02/2026", "20:30", "Claro Arena", UC, 3, 1, COQ, J, ""),
    (4, "22/02/2026", "12:00", "La Portada", LSE, 1, 1, UDEC, J, ""),
    (4, "22/02/2026", "18:00", "La Florida", AUD, 1, 0, EVE, J, ""),
    (4, "22/02/2026", "20:30", "Estadio Nacional", UCH, 2, 2, LIM, J, ""),

    (5, "27/02/2026", "18:00", "El Cobre", COB, 0, 1, LSE, J, ""),
    (5, "27/02/2026", "20:30", "Nicolas Chahuan", ULC, 3, 0, AUD, J, ""),
    (5, "28/02/2026", "12:00", "Sanchez Rumoroso", COQ, 0, 1, DCO, J, ""),
    (5, "28/02/2026", "18:00", "Lucio Farina", LIM, 3, 0, HUA, J, ""),
    (5, "28/02/2026", "20:30", "La Cisterna", PAL, 4, 2, OHI, J, ""),
    (5, "01/03/2026", "12:00", "Ester Roa", UDEC, 0, 3, EVE, J, ""),
    (5, "01/03/2026", "18:00", "Monumental", CC, 0, 1, UCH, J, "Superclasico 199"),
    (5, "01/03/2026", "20:30", "Nelson Oyarzun", NUB, 1, 2, UC, J, ""),

    (6, "06/03/2026", "18:00", "La Portada", LSE, 3, 0, ULC, J, ""),
    (6, "06/03/2026", "20:30", "Ester Roa", DCO, 0, 2, NUB, J, ""),
    (6, "07/03/2026", "12:00", "Huachipato CAP Acero", HUA, 1, 3, COQ, J, ""),
    (6, "07/03/2026", "12:00", "Sausalito", EVE, 1, 0, LIM, J, ""),
    (6, "07/03/2026", "18:00", "La Florida", AUD, 0, 1, CC, J, ""),
    (6, "07/03/2026", "20:30", "El Teniente", OHI, 1, 0, UC, J, ""),
    (6, "08/03/2026", "20:30", "La Cisterna", PAL, 4, 2, COB, J, ""),
    (6, "09/03/2026", "20:30", "Estadio Nacional", UCH, 1, 1, UDEC, J, ""),

    (7, "13/03/2026", "20:00", "La Florida", AUD, 3, 0, DCO, J, ""),
    (7, "14/03/2026", "18:00", "Sanchez Rumoroso", COQ, 0, 1, UCH, J, ""),
    (7, "14/03/2026", "20:30", "Claro Arena", UC, 2, 2, EVE, J, ""),
    (7, "15/03/2026", "12:00", "Ester Roa", UDEC, 1, 0, PAL, J, ""),
    (7, "15/03/2026", "18:00", "El Cobre", COB, 2, 5, LIM, J, ""),
    (7, "15/03/2026", "20:30", "Nelson Oyarzun", NUB, 2, 2, LSE, J, ""),
    (7, "16/03/2026", "18:00", "Nicolas Chahuan", ULC, 3, 3, OHI, J, "Fuente indica 'Nelson Oyarzun'; se corrige a Nicolas Chahuan (localia de U. La Calera)"),
    (7, "16/03/2026", "20:30", "Monumental", CC, 2, 0, HUA, J, ""),

    (8, "02/04/2026", "18:00", "Claro Arena", UC, 6, 1, PAL, J, ""),
    (8, "03/04/2026", "17:30", "Sanchez Rumoroso", COQ, 3, 2, COB, J, ""),
    (8, "03/04/2026", "20:00", "El Teniente", OHI, 2, 1, AUD, J, ""),
    (8, "04/04/2026", "17:30", "Lucio Farina", LIM, 4, 0, ULC, J, ""),
    (8, "04/04/2026", "20:00", "Sausalito", EVE, 0, 0, NUB, J, ""),
    (8, "05/04/2026", "15:30", "Ester Roa", DCO, 0, 1, CC, J, ""),
    (8, "05/04/2026", "18:00", "Estadio Nacional", UCH, 4, 0, LSE, J, ""),
    (8, "06/04/2026", "20:00", "Huachipato CAP Acero", HUA, 5, 1, UDEC, J, ""),

    (9, "10/04/2026", "20:00", "El Teniente", OHI, 0, 2, HUA, J, ""),
    (9, "11/04/2026", "15:00", "La Portada", LSE, 1, 0, EVE, J, ""),
    (9, "11/04/2026", "17:30", "La Florida", AUD, 3, 4, UC, J, ""),
    (9, "11/04/2026", "20:00", "La Cisterna", PAL, 1, 0, LIM, J, ""),
    (9, "12/04/2026", "17:30", "Nelson Oyarzun", NUB, 1, 0, UCH, J, ""),
    (9, "12/04/2026", "20:00", "Ester Roa", UDEC, 1, 0, COB, J, ""),
    (9, "13/04/2026", "20:00", "Nicolas Chahuan", ULC, 1, 0, DCO, J, ""),
    (9, "03/05/2026", "17:30", "Monumental", CC, 3, 1, COQ, J, "Partido reprogramado"),

    (10, "17/04/2026", "20:00", "Lucio Farina", LIM, 3, 0, UDEC, J, ""),
    (10, "18/04/2026", "17:30", "Sausalito", EVE, 0, 0, UCH, J, ""),
    (10, "18/04/2026", "20:00", "Ester Roa", DCO, 3, 3, LSE, J, ""),
    (10, "19/04/2026", "12:30", "Sanchez Rumoroso", COQ, 1, 1, NUB, J, ""),
    (10, "19/04/2026", "15:30", "El Cobre", COB, 2, 3, OHI, J, ""),
    (10, "19/04/2026", "18:30", "Monumental", CC, 0, 1, PAL, J, ""),
    (10, "19/04/2026", "20:45", "Huachipato CAP Acero", HUA, 3, 2, AUD, J, ""),
    (10, "20/04/2026", "20:00", "Claro Arena", UC, 1, 2, ULC, J, ""),

    (11, "23/04/2026", "20:00", "La Cisterna", PAL, 0, 1, DCO, J, ""),
    (11, "24/04/2026", "18:00", "Nicolas Chahuan", ULC, 1, 2, COQ, J, ""),
    (11, "24/04/2026", "20:30", "La Florida", AUD, 2, 2, LIM, J, ""),
    (11, "25/04/2026", "15:00", "Nelson Oyarzun", NUB, 0, 2, OHI, J, ""),
    (11, "25/04/2026", "18:00", "Estadio Nacional", UCH, 1, 0, UC, J, "Clasico Universitario 202"),
    (11, "26/04/2026", "12:30", "La Portada", LSE, 0, 0, HUA, J, ""),
    (11, "26/04/2026", "15:00", "Ester Roa", UDEC, 1, 2, CC, J, ""),
    (11, "26/04/2026", "17:30", "Sausalito", EVE, 3, 1, COB, J, ""),

    (12, "15/05/2026", "20:00", "Santa Laura", PAL, 5, 1, LSE, J, ""),
    (12, "15/05/2026", "20:00", "Sanchez Rumoroso", COQ, 3, 0, AUD, J, ""),
    (12, "16/05/2026", "17:30", "El Teniente", OHI, 0, 1, UDEC, J, ""),
    (12, "16/05/2026", "20:00", "Lucio Farina", LIM, 0, 2, UC, J, ""),
    (12, "17/05/2026", "12:30", "Huachipato CAP Acero", HUA, 3, 1, ULC, J, ""),
    (12, "17/05/2026", "15:00", "El Cobre", COB, 1, 0, UCH, J, ""),
    (12, "17/05/2026", "17:30", "Monumental", CC, 6, 2, NUB, J, ""),
    (12, "17/05/2026", "20:00", "Ester Roa", DCO, 0, 2, EVE, J, ""),

    (13, "22/05/2026", "20:00", "Sausalito", EVE, 1, 1, COQ, J, ""),
    (13, "23/05/2026", "12:30", "La Florida", AUD, 2, 1, COB, J, ""),
    (13, "23/05/2026", "15:00", "Nelson Oyarzun", NUB, 2, 2, UDEC, J, ""),
    (13, "23/05/2026", "20:00", "Nicolas Chahuan", ULC, 1, 2, PAL, J, ""),
    (13, "24/05/2026", "12:30", "Ester Roa", DCO, 2, 0, HUA, J, ""),
    (13, "24/05/2026", "15:00", "La Portada", LSE, 4, 1, LIM, J, ""),
    (13, "24/05/2026", "18:00", "Claro Arena", UC, 1, 2, CC, J, ""),
    (13, "18/06/2026", "20:00", "Estadio Nacional", UCH, 2, 0, OHI, J, "Partido reprogramado"),

    (14, "29/05/2026", "18:00", "El Cobre", COB, 0, 1, NUB, J, ""),
    (14, "29/05/2026", "20:30", "Ester Roa", UDEC, 0, 0, ULC, J, ""),
    (14, "30/05/2026", "15:00", "La Portada", LSE, 2, 4, CC, J, ""),
    (14, "30/05/2026", "17:30", "Estadio Nacional", UCH, 2, 1, DCO, J, ""),
    (14, "31/05/2026", "12:30", "Lucio Farina", LIM, 2, 3, COQ, J, ""),
    (14, "31/05/2026", "15:00", "Huachipato CAP Acero", HUA, 0, 3, UC, J, ""),
    (14, "31/05/2026", "17:30", "El Teniente", OHI, 2, 3, EVE, J, ""),
    (14, "31/05/2026", "20:00", "La Cisterna", PAL, 0, 0, AUD, J, ""),

    (15, "12/06/2026", "20:00", "La Florida", AUD, 1, 1, LSE, J, ""),
    (15, "13/06/2026", "12:30", "Sanchez Rumoroso", COQ, 0, 0, OHI, J, ""),
    (15, "13/06/2026", "15:00", "Sausalito", EVE, 1, 2, PAL, J, ""),
    (15, "13/06/2026", "17:30", "Monumental", CC, 3, 0, COB, J, ""),
    (15, "13/06/2026", "20:00", "Nelson Oyarzun", NUB, 2, 2, HUA, J, ""),
    (15, "14/06/2026", "12:30", "Ester Roa", DCO, 3, 2, LIM, J, ""),
    (15, "14/06/2026", "15:00", "Nicolas Chahuan", ULC, 2, 2, UCH, J, ""),
    (15, "14/06/2026", "17:30", "Claro Arena", UC, 5, 1, UDEC, J, ""),

    (16, "24/07/2026", "20:30", "Monumental", CC, 3, 1, LIM, J, ""),
    (16, "25/07/2026", "17:30", "Huachipato CAP Acero", HUA, 3, 3, COB, J, ""),
    (16, "25/07/2026", "20:00", "Claro Arena", UC, 3, 3, LSE, J, ""),
    (16, "26/07/2026", "15:00", "Nelson Oyarzun", NUB, 2, 0, PAL, J, ""),
    (16, "26/07/2026", "17:30", "La Florida", AUD, 1, 2, UCH, J, ""),
    (16, "26/07/2026", "20:30", "Ester Roa", DCO, 2, 0, OHI, J, ""),
    (16, "27/07/2026", "19:00", "Nicolas Chahuan", ULC, 1, 1, EVE, J, ""),
    (16, "02/09/2026", "18:00", "Sanchez Rumoroso", COQ, 1, 0, UDEC, J, "Partido reprogramado"),

    (17, "31/07/2026", "20:00", "Ester Roa", UDEC, 0, 1, AUD, J, ""),
    (17, "01/08/2026", "12:30", "El Cobre", COB, 4, 0, ULC, J, ""),
    (17, "01/08/2026", "15:00", "Sausalito", EVE, 3, 4, CC, J, ""),
    (17, "01/08/2026", "17:30", "La Cisterna", PAL, 2, 1, COQ, J, ""),
    (17, "02/08/2026", "12:30", "Ester Roa", DCO, 3, 0, UC, J, ""),
    (17, "02/08/2026", "15:00", "La Portada", LSE, 1, 2, OHI, J, ""),
    (17, "02/08/2026", "17:30", "Estadio Nacional", UCH, 2, 0, HUA, J, ""),
    (17, "02/09/2026", "20:30", "Lucio Farina", LIM, 2, 0, NUB, J, "Partido reprogramado"),

    (18, "07/08/2026", "20:30", "Claro Arena", UC, 2, 0, COB, J, ""),
    (18, "08/08/2026", "15:00", "Huachipato CAP Acero", HUA, 1, 4, EVE, J, ""),
    (18, "08/08/2026", "17:30", "Sanchez Rumoroso", COQ, 1, 1, LSE, J, ""),
    (18, "09/08/2026", "12:30", "Ester Roa", DCO, 1, 0, UDEC, J, ""),
    (18, "09/08/2026", "15:00", "El Teniente", OHI, 1, 3, LIM, J, ""),
    (18, "09/08/2026", "17:30", "Nicolas Chahuan", ULC, 1, 2, CC, J, ""),
    (18, "09/08/2026", "20:00", "Estadio Nacional", UCH, 2, 1, PAL, J, ""),
    (18, "10/08/2026", "20:00", "La Florida", AUD, 2, 2, NUB, J, ""),

    (19, "14/08/2026", "19:00", "Ester Roa", UDEC, 0, 2, LSE, J, ""),
    (19, "15/08/2026", "17:30", "Lucio Farina", LIM, 1, 3, UCH, J, ""),
    (19, "15/08/2026", "20:00", "Sausalito", EVE, 1, 1, AUD, J, ""),
    (19, "16/08/2026", "12:30", "Nelson Oyarzun", NUB, 2, 1, ULC, J, ""),
    (19, "16/08/2026", "15:00", "El Cobre", COB, 0, 2, DCO, J, ""),
    (19, "16/08/2026", "17:30", "Monumental", CC, 2, 2, OHI, J, ""),
    (19, "17/08/2026", "20:30", "La Cisterna", PAL, 5, 1, HUA, J, ""),
    (19, "26/08/2026", "18:00", "Sanchez Rumoroso", COQ, 1, 2, UC, J, "Partido reprogramado"),

    (20, "21/08/2026", "20:30", "La Florida", AUD, 0, 0, ULC, J, ""),
    (20, "22/08/2026", "17:30", "Huachipato CAP Acero", HUA, 1, 3, LIM, J, ""),
    (20, "22/08/2026", "20:00", "Claro Arena", UC, 1, 2, NUB, J, ""),
    (20, "23/08/2026", "12:00", "La Portada", LSE, 3, 3, COB, J, ""),
    (20, "23/08/2026", "12:00", "Ester Roa", DCO, 1, 1, COQ, J, ""),
    (20, "23/08/2026", "15:00", "Estadio Nacional", UCH, 1, 2, CC, J, "Superclasico 200"),
    (20, "23/08/2026", "19:00", "El Teniente", OHI, 0, 1, PAL, J, ""),
    (20, "24/08/2026", "19:30", "Sausalito", EVE, 3, 1, UDEC, J, ""),

    (21, "28/08/2026", "18:30", "El Cobre", COB, 2, 0, PAL, J, ""),
    (21, "29/08/2026", "17:30", "Lucio Farina", LIM, 0, 3, EVE, J, ""),
    (21, "29/08/2026", "20:00", "Nelson Oyarzun", NUB, 0, 1, DCO, J, ""),
    (21, "30/08/2026", "15:00", "Ester Roa", UDEC, 2, 1, UCH, J, ""),
    (21, "30/08/2026", "17:30", "Monumental", CC, 5, 1, AUD, J, ""),
    (21, "30/08/2026", "20:00", "Sanchez Rumoroso", COQ, 0, 1, HUA, S,
     "SUSPENDIDO al minuto 68 (0-1, gol de Sergio Nunez) por bombas de estruendo lanzadas desde la galeria local que afectaron al arquero Christian Bravo. La ANFP resolvio reanudar los 22 minutos restantes. NO computa en la tabla"),
    (21, "31/08/2026", "18:15", "Nicolas Chahuan", ULC, 0, 1, LSE, J, ""),
    (21, "31/08/2026", "20:45", "Claro Arena", UC, 3, 2, OHI, J, ""),
]

GOLEADORES = [
    ("Fernando Zampedri", UC, 22),
    ("Javier Correa", CC, 12),
    ("Daniel Castro", LIM, 11),
    ("Nelson Da Silva", PAL, 9),
    ("Lionel Altamirano", HUA, 9),
    ("Alan Medina", EVE, 9),
    ("Sebastian Saez", ULC, 8),
    ("Justo Giani", UC, 8),
    ("Eduardo Vargas", UCH, 8),
    ("Maximiliano Romero", CC, 8),
    ("Steffan Pino", COB, 7),
    ("Joaquin Larrivey", DCO, 7),
    ("Nicolas Montiel", EVE, 7),
    ("Leandro Hernandez", CC, 7),
    ("Jeisson Vargas", LSE, 7),
    ("Nicolas Johansen", COQ, 7),
    ("Arnaldo Castillo", OHI, 7),
]
