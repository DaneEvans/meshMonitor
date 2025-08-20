# Initial python scratch file - Console output of battery levels etc accross all of your favorited nodes.


import meshtastic
import meshtastic.serial_interface
from pubsub import pub

def onReceive(packet, interface): # called when a packet arrives
    print(f"Received: {packet}")

def onConnection(interface, topic=pub.AUTO_TOPIC): # called when we (re)connect to the radio
    # defaults to broadcast, specify a destination ID if you wish
    print("Connected")
    interface.sendText("hello mesh")

pub.subscribe(onReceive, "meshtastic.receive")
pub.subscribe(onConnection, "meshtastic.connection.established")
# By default will try to find a meshtastic device, otherwise provide a device path like /dev/ttyUSB0
interface = meshtastic.serial_interface.SerialInterface()

def getUptimeString(node):
    outStr = f"up {node['deviceMetrics']['uptimeSeconds']/3600:7.1f} hrs"
    return outStr

def getBatteryLevels(node):
    isCharging = node['deviceMetrics']['batteryLevel'] == 101
    outStr = ""
    if isCharging:
        outStr += "Chg"
    else:
        outStr += f"{node['deviceMetrics']['batteryLevel']}%"
    outStr += f", {node['deviceMetrics']['voltage']:.3f}V "
    return outStr

def getBatts(interface):
    for nodeId in interface.nodes:
        node = interface.nodes[nodeId]
        node_keys = node.keys()
        # print(node_keys)
        # if "deviceMetrics" in node_keys:
        #     print(node['deviceMetrics'])
        if "isFavorite" in node_keys:
            # print(f"{node_keys}")
            print(f"{nodeId}  {node['user']['longName']:20} - {node['user']['hwModel']:15}  : {getBatteryLevels(node)} : {getUptimeString(node)}")

def findNonFav(interface):
    for nodeId in interface.nodes:
        node = interface.nodes[nodeId]
        node_keys = node.keys()
        # print(node_keys)
        # if "deviceMetrics" in node_keys:
        #     print(node['deviceMetrics'])
        if "isFavorite" not in node_keys:
            print(f"{nodeId}  {node['user']['longName']:20} - {node['user']['hwModel']:15}")


getBatts(interface)
print("")
findNonFav(interface)
