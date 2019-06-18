
import httplib
import json
import time

class RutasAutomaticas(object):
 
    def __init__(self, server):
        self.server = server
 
    def set(self, data):
        ret = self.rest_call(data, 'POST')
        return ret[0] == 200
 
    def remove(self, objtype, data):
        ret = self.rest_call(data, 'DELETE')
        return ret[0] == 200

    def get(self, data):
        ret = self.rest_call(data, 'GET')
        return json.loads(ret[2])

    def rest_call(self, data, action):
	if (action == 'GET') :
		path = data
		body = json.dumps({})
	if (action == 'POST') :
		path = data[0]
		body = json.dumps(data[1])
        headers = {
            'Content-type': 'application/json',
            'Accept': 'application/json',
            }
        conn = httplib.HTTPConnection(self.server, 8080)
        conn.request(action, path, body, headers)
        response = conn.getresponse()
        ret = (response.status, response.reason, response.read())
        conn.close()
        return ret

#Creacion objeto que accede a la API REST 
pusher = RutasAutomaticas('127.0.0.1')

#Metodo para conocer el numero de enlaces en la red
def getNumEnlaces():
	global nEnlaces
	#Consulta a la API REST
	salida_enlaces = pusher.get('/wm/topology/links/json' )
	nEnlaces = len(salida_enlaces)
	return nEnlaces
#Metodo para conocer los sw la red
def getSwitch():
	global swList
	swList = []
	salida_sw = pusher.get('/wm/core/controller/switches/json')
	for sw in salida_sw:
		swList.append(str(sw['switchDPID']))
	return swList

#Metodo para concoer el numero de equipos conectados a la red
def getEquipos():
	#Consulta a la API REST
	salida_device = pusher.get('/wm/device/')

	#equipos: array con tres arrays: sw, puerto y ipv4 del equipo en cuestion
	#ejemplo: [[00:00:00:00:00:00:00:01,00:00:00:00:00:00:00:03],[1,3],[10.0.0.1,10.0.0.2]]
	global equipos 
	equipos = [[],[],[]]

	#Rellenar array equipos
	for device in salida_device['devices']:
		attPoint = device['attachmentPoint']
		ipv4 = device['ipv4']
		if(attPoint!=[] and ipv4!= []):
			equipos[0].append(str(attPoint[0]['switch']))
			equipos[1].append(str(attPoint[0]['port']))
			equipos[2].append(str(ipv4[0]))

	global nEquipos
	nEquipos = len(equipos[1])
	return nEquipos

#Metodo para conocer las dos rutas 'optimas entre cada par de hosts priRs y rutasS
def getRutas():
	#priRs y rutasS: array de arrays, cada array es una ruta completa, los primeros elementos de la ruta son un diccionario con switch y port y los dos 'ultimos el host origen y el destino
	global priRs
	priRs = []
	
	global rutasS
	rutasS = []
	for i in range(len(equipos[0])-1):
		for j in range(i+1, len(equipos[0])):
			#data = [:01,:03,1,3,10.0.0.1,10.0.03]	
			data = [equipos[0][i],equipos[0][j],equipos[1][i],equipos[1][j],equipos[2][i],equipos[2][j]]
			
			if(equipos[0][i] != equipos[0][j]):
				json_results = pusher.get('/wm/routing/paths/'+data[0]+'/'+data[1]+'/2/json')
				pathP = json_results["results"][0]["path"]
				priR = [{'switch': data[0],'port': data[2]}]
				for p in pathP:
					priR.append({'switch': p['dpid'],'port': p['port']})
				priR.append({'switch': data[1],'port': data[3]})
				priR.append(data[4])
				priR.append(data[5])
				priRs.append(priR)
				
				if(len(json_results["results"]) > 1):
					pathS = json_results["results"][1]["path"]
					rutaS = [{'switch': data[0],'port': data[2]}]
					for p in pathS:
						rutaS.append({'switch': p['dpid'],'port': p['port']})
					rutaS.append({'switch': data[1],'port': data[3]})
					rutaS.append(data[4])
					rutaS.append(data[5])
					rutasS.append(rutaS)
				else:
					print('Una unica ruta entre '+data[4]+' y '+data[5]+':')
					rutaUnica = priRs[len(priRs)-1]
					salida = ''
					for s in range(0,len(rutaUnica)-2,2):
						if(salida==''):
							salida += 's'
						else:
							salida += '-s'
						salida += rutaUnica[s]["switch"][len(rutaUnica[s]["switch"])-1]
					print salida				
										
					rutasS.append(rutaUnica)
				
				
			else:
				json_results = pusher.get('/wm/routing/path/'+data[0]+'/'+data[2]+'/'+data[1]+'/'+data[3]+'/json')

				priRs.append(json_results["results"])
				priRs[len(priRs)-1].append(data[4])
				priRs[len(priRs)-1].append(data[5])
			
				rutasS.append(priRs[len(priRs)-1])	


#Metodo para crear los flujos correspondientes a las rutas primarias priRs
def getFlowsInicial():
	
	#flowsI: array con todos los flujos a implantar
	global initialFlows
	initialFlows = []
	
	#name: variable para asignar un nombre unico a cada flujo
	name = 0

	#Creacion y asignacion de flujos
	for ruta in priRs:
		origen = ruta[len(ruta)-2]
		destino = ruta[len(ruta)-1]
		for p in range(0,len(ruta)-2,2):
			switch = ruta[p]['switch']
			port1 = ruta[p]['port']
			port2 = ruta[p+1]['port']

			initialFlows.append({'switch':str(switch),
					"name":"flow_mod_"+str(name),
					"cookie":"0",
					"priority":"32768",
					"eth_type":"0x0800",
					"in_port":str(port1),
					"ipv4_dst":str(destino),
					"active":"true",
					"actions":"output="+str(port2)})
			name = name + 1

			initialFlows.append({'switch':str(switch),
					"name":"flow_mod_"+str(name),
					"cookie":"0",
					"priority":"32768",
					"eth_type":"0x0800",
					"in_port":str(port2),
					"ipv4_dst":str(origen),
					"active":"true",
					"actions":"output="+str(port1)})
			name = name + 1	

#Metodo para crear los flujos correspondientes a las rutas primarias priRs y secundarias rutasS
def getFlowsPrioridad():
	
	#priorityFlows: array con todos los flujos a implantar
	global priorityFlows
	priorityFlows = []
	
	#name: variable para asignar un nombre unico a cada flujo
	name = 0

	#Creacion y asignacion de flujos Primarios, nueva condicion: tp_dst
	for ruta in priRs:
		origen = ruta[len(ruta)-2]
		destino = ruta[len(ruta)-1]
		for p in range(0,len(ruta)-2,2):
			switch = ruta[p]['switch']
			port1 = ruta[p]['port']
			port2 = ruta[p+1]['port']

			priorityFlows.append({'switch':str(switch),
					"name":"flow_mod_"+str(name),
					"cookie":"0",
					"priority":"32768",
					"eth_type":"0x0800",
					"ip_proto":"0x11",
					"tp_dst":"5001",
					"in_port":str(port1),
					"ipv4_dst":str(destino),
					"active":"true",
					"actions":"output="+str(port2)})
			name = name + 1

			priorityFlows.append({'switch':str(switch),
					"name":"flow_mod_"+str(name),
					"cookie":"0",
					"priority":"32768",
					"eth_type":"0x0800",
					"ip_proto":"0x11",
					"tp_dst":"5001",
					"in_port":str(port2),
					"ipv4_dst":str(origen),
					"active":"true",
					"actions":"output="+str(port1)})
			name = name + 1
	
	#Creacion y asignacion de flujos secundarios	
	for ruta in rutasS:
		origen = ruta[len(ruta)-2]
		destino = ruta[len(ruta)-1]
		for p in range(0,len(ruta)-2,2):
			switch = ruta[p]['switch']
			port1 = ruta[p]['port']
			port2 = ruta[p+1]['port']

			priorityFlows.append({'switch':str(switch),
					"name":"flow_mod_"+str(name),
					"cookie":"0",
					"priority":"32768",
					"eth_type":"0x0800",
					"in_port":str(port1),
					"ipv4_dst":str(destino),
					"active":"true",
					"actions":"output="+str(port2)})
			name = name + 1

			priorityFlows.append({'switch':str(switch),
					"name":"flow_mod_"+str(name),
					"cookie":"0",
					"priority":"32768",
					"eth_type":"0x0800",
					"in_port":str(port2),
					"ipv4_dst":str(origen),
					"active":"true",
					"actions":"output="+str(port1)})
			name = name + 1	


#Metodo para permitir consulta bw y conocer el numero de enlaces	
def previo():
	pusher.set(['/wm/routing/metric/json', {"metric":"speed_utilization"} ])
	getNumEnlaces()

#Metodo para insertar los flujos creados Inicialmente
def launch():
	print('Ejecutando launch')
	getEquipos()
	getRutas()
	getFlowsInicial()
	getSwitch()
	#Borrar flujos anteriores con: /wm/staticflowpusher/clear/all/json
	pusher.get('/wm/staticflowpusher/clear/all/json')
	for flow in initialFlows:
		pusher.set(['/wm/staticentrypusher/json', flow])

#Metodo para insertar los flujos creados tras sobrepasar el bw permitido
def recalcular():
	print('Ejecutando recalcular')
	getEquipos()
	getRutas()
	getFlowsPrioridad()
	getSwitch()
	#Borrar flujos anteriores con: /wm/staticflowpusher/clear/all/json
	pusher.get('/wm/staticflowpusher/clear/all/json')
	for flow in priorityFlows:
		pusher.set(['/wm/staticentrypusher/json', flow])
	
	
#Lanzamiento del programa		
previo()		
launch()
qosActivo = 0
#Consultas al sistema cada 10 segundos
while (1==1):
	#Consulta numero de enlaces, equipos y switches
	nEnlacesViejo = nEnlaces
	getNumEnlaces()
	nEquiposViejo = nEquipos
	getEquipos()
	swListVieja = swList
	getSwitch()
	if (nEnlaces != nEnlacesViejo or nEquipos!= nEquiposViejo or len(swList) != len(swListVieja)):
		#Recalcular topologia y rutas
		print('	Detectado cambio topologia')
		if (qosActivo == 1):
			recalcular()
		else:		
			launch()	

	#Consulta Bandwidth de todos los puertos
	print('Comprobando bw') 
	port = 1
	salida = []
	while (len(salida)==0 or salida[len(salida)-1] != []):
		salida.append(pusher.get('/wm/statistics/bandwidth/all/'+str(port)+'/json'))
		port = port + 1
	salida.pop(len(salida)-1)	
	
	superado = 0
	for puerto in salida:
		for dato in puerto:
			if ((int(dato['bits-per-second-tx'])>int(dato['link-speed-bits-per-second'])*0.6) or (int(dato['bits-per-second-rx'])>int(dato['link-speed-bits-per-second'])*0.6)):
				print('	Limite superado')
				print('  Switch: ' + dato['dpid'])
				print('  Port: ' + dato['port'])
				qosActivo = 1
				superado = 1
				
	if(superado == 1):
		recalcular()
	else:		
		print('Ningun enlace supera el limite de trafico')

	time.sleep(10)

