from pysnmp.hlapi.asyncio import *

import asyncio

from config import CURRENT_IP
from config import COMMUNITY
from config import PORT
from config import SNMP_VERSION


class SNMPClient:

    def __init__(self):

        self.ip = CURRENT_IP

    def set_ip(self, ip):
        print(f"[SNMP] Changing IP from {self.ip} to {ip}")
        self.ip = ip
        print(f"[SNMP] Current IP is now: {self.ip}")

    async def get(self, oid):

        iterator = get_cmd(
            SnmpEngine(),
            CommunityData(COMMUNITY, mpModel=SNMP_VERSION),
            await UdpTransportTarget.create((self.ip, PORT), timeout=0.5, retries=0),
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
        )

        errorIndication, errorStatus, errorIndex, varBinds = await iterator

        if errorIndication:
            return None, str(errorIndication)

        if errorStatus:
            return None, str(errorStatus)

        for varBind in varBinds:
            return str(varBind[1]), None

        return None, "Unknown Error"

    async def set(self, oid, value):

        if isinstance(value, int):
            data = Integer(value)
        else:
            data = OctetString(str(value))

        iterator = set_cmd(
            SnmpEngine(),
            CommunityData(COMMUNITY, mpModel=SNMP_VERSION),
            await UdpTransportTarget.create((self.ip, PORT), timeout=0.5, retries=0),
            ContextData(),
            ObjectType(ObjectIdentity(oid), data),
        )

        errorIndication, errorStatus, errorIndex, varBinds = await iterator

        if errorIndication:
            return False, str(errorIndication)

        if errorStatus:
            return False, str(errorStatus)

        return True, None

    def read(self, oid):
        print(f"[SNMP READ] IP={self.ip}, OID={oid}")

        value, error = asyncio.run(self.get(oid))

        print(f"      VALUE = {value}")
        print(f"      ERROR = {error}")

        return value, error

    def write(self, oid, value):

        return asyncio.run(self.set(oid, value))

    def test(self):

        value, error = self.read("1.3.6.1.2.1.1.1.0")

        return error is None


client = SNMPClient()
