import time

import meshtastic
import meshtastic.tcp_interface
import meshtastic.serial_interface
from pubsub import pub
from nicegui import ui


# interface = meshtastic.serial_interface.SerialInterface()
def onReceive(packet, interface): # called when a packet arrives
    print(f"Received: {packet}")

def onConnection(interface, topic=pub.AUTO_TOPIC): # called when we (re)connect to the radio
    # defaults to broadcast, specify a destination ID if you wish
    print("Connected")
    # interface.sendText("hello mesh")
# pub.subscribe(onReceive, "meshtastic.receive")
# pub.subscribe(onConnection, "meshtastic.connection.established")
# time.sleep(4)

class MeshInterface:
    def __init__(self, interface):
        self.number = 1
        self.interface = interface

    def getUptimeString(self, node):
        outStr = f"up {node['deviceMetrics']['uptimeSeconds']/3600:7.1f} hrs"
        return outStr

    def getBatteryLevels(self, node):
        isCharging = node['deviceMetrics']['batteryLevel'] == 101
        outStr = ""
        if isCharging:
            outStr += " Chg"
        else:
            outStr += f"{node['deviceMetrics']['batteryLevel']:3}%"
        outStr += f", {node['deviceMetrics']['voltage']:.3f}V "
        return outStr

    def getBatts_string(self, whole_mesh = False):
        for nodeId in self.interface.nodes:
            node = self.interface.nodes[nodeId]
            node_keys = node.keys()
            # print(node_keys)
            # if "deviceMetrics" in node_keys:
            #     print(node['deviceMetrics'])
            if whole_mesh and "deviceMetrics" in node_keys:
                print(f"{nodeId}  {node['user']['longName']:25} - {node['user']['hwModel']:21} : {self.getBatteryLevels(node)} : {self.getUptimeString(node)}")

            elif "isFavorite" in node_keys:
                print(f"{nodeId}  {node['user']['longName']:25} - {node['user']['hwModel']:21} : {self.getBatteryLevels(node)} : {self.getUptimeString(node)}")

    def findNonFav_string(self):
        for nodeId in self.interface.nodes:
            node = self.interface.nodes[nodeId]
            node_keys = node.keys()
            # print(node_keys)
            # if "deviceMetrics" in node_keys:
            #     print(node['deviceMetrics'])
            if "isFavorite" not in node_keys:
                print(f"{nodeId}  {node['user']['longName']:20} - {node['user']['hwModel']:15}")

    def findNonFavs(self):
        nodes=[]
        for nodeId in self.interface.nodes:
            node = self.interface.nodes[nodeId]
            node_keys = node.keys()
            # print(node_keys)
            # if "deviceMetrics" in node_keys:
            #     print(node['deviceMetrics'])
            if "isFavorite" not in node_keys:
                print(f"{nodeId}  {node['user']['longName']:20} - {node['user']['hwModel']:15}")
                nodes.append(node)
        return nodes

    def findFavs(self):
        nodes = []
        for nodeId in self.interface.nodes:
            node = self.interface.nodes[nodeId]
            node_keys = node.keys()
            # print(node_keys)
            # if "deviceMetrics" in node_keys:
            #     print(node['deviceMetrics'])
            if "isFavorite" in node_keys:
                print(f"{nodeId}  {node['user']['longName']:20} - {node['user']['hwModel']:15}")
                nodes.append(node)
        return nodes


interface = meshtastic.tcp_interface.TCPInterface("192.168.0.114")
# interface = meshtastic.serial_interface.SerialInterface()


def text_oneshot(mesh_interface):
# Text based version:
    network = MeshInterface(mesh_interface)
    network.getBatts_string(whole_mesh = True)
    print("")
    # print("The following aren't favourites: ")
    # network.findNonFavs()


def continuous_text(mesh_interface):
    network = MeshInterface(mesh_interface)
    while True:
        curr_time = time.strftime("%H:%M:%S", time.localtime())
        print("Current Time is :", curr_time)
        network.getBatts_string(whole_mesh = True)
        print("")
        time.sleep(30)


# text_oneshot(interface)
continuous_text(interface)   

demo = None
# demo = MeshInterface(interface)

ui.connected = False

def openSerialPort() -> None:
    demo = MeshInterface(interface)
    demo.getBatts_string()
    ui.connected = True

with ui.column().bind_visibility_from(ui.connected, 'value'):
    ui.button('Open Serial Port', on_click=openSerialPort)
# with ui.column().bind_visibility_from(ui.connected, 'value'):
#     ui.button('Close Serial Port', on_click=openSerialPort)

    # ui.slider(min=1, max=3).bind_value(demo, 'number')
#     ui.toggle({1: 'A', 2: 'B', 3: 'C'}).bind_value(demo, 'number')
#     ui.number().bind_value(demo, 'number')
v = ui.checkbox('See All', value=False)

# with ui.column().bind_visibility_from(v, 'value'):
#     for node in demo.findNonFavs():
# #     #     with ui.row():
#             ui.button(node['user']['longName'], on_click=lambda: ui.notify('Click'))
#     ui.slider(min=1, max=3).bind_value(demo, 'number')
#     # ui.toggle({1: 'A', 2: 'B', 3: 'C'}).bind_value(demo, 'number')
#     # ui.number().bind_value(demo, 'number')
#
ui.run()

# interface = meshtastic.serial_interface.SerialInterface()
