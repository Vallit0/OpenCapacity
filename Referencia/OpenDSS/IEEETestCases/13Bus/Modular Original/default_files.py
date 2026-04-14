# Contenido por defecto para IEEELineCodes.DSS
DEFAULT_LINECODES = """
~ ---- LineCode Definition for IEEE 13 Node Test Feeder ----

New LineCode.601 nphases=4 units=mi r1=0.0001 x1=0.0001 r0=0.0001 x0=0.0001
New LineCode.602 nphases=4 units=mi r1=0.0001 x1=0.0001 r0=0.0001 x0=0.0001
New LineCode.603 nphases=4 units=mi r1=0.0001 x1=0.0001 r0=0.0001 x0=0.0001
New LineCode.604 nphases=4 units=mi r1=0.0001 x1=0.0001 r0=0.0001 x0=0.0001

New LineCode.1 nphases=3 units=mi 
~ rmatrix (ohms/mile) [0.0001, 0.0001, 0.0001; 0.0001, 0.0001, 0.0001; 0.0001, 0.0001, 0.0001]
~ xmatrix (ohms/mile) [0.0001, 0.0001, 0.0001; 0.0001, 0.0001, 0.0001; 0.0001, 0.0001, 0.0001]
"""

# Contenido por defecto para IEEE13Node_BusXY.csv
DEFAULT_BUSXY = """Bus,X,Y
650,100,100
RG60,150,120
633,200,150
634,250,180
645,300,200
646,350,220
692,400,250
675,450,280
611,500,300
652,550,320
670,600,350
671,650,380
684,700,400
"""