from pysnmp.hlapi.asyncio import (
    SnmpEngine,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity,
    get_cmd,
    set_cmd,
)

from pysnmp.proto.rfc1902 import (
    Integer,
    OctetString,
)

import asyncio

from config import (
    CURRENT_IP,
    COMMUNITY,
    PORT,
    SNMP_VERSION,
)


class SNMPClient:

    TIMEOUT = 1.5
    RETRIES = 1

    def __init__(self):

        self.ip = CURRENT_IP

    def set_ip(self, ip):

        print(f"[SNMP] Changing IP " f"from {self.ip} to {ip}")

        self.ip = ip

        print(f"[SNMP] Current IP is now: " f"{self.ip}")

    async def get(self, oid):

        try:

            transport = await UdpTransportTarget.create(
                (self.ip, PORT),
                timeout=self.TIMEOUT,
                retries=self.RETRIES,
            )

            iterator = get_cmd(
                SnmpEngine(),
                CommunityData(
                    COMMUNITY,
                    mpModel=SNMP_VERSION,
                ),
                transport,
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
            )

            errorIndication, errorStatus, errorIndex, varBinds = await iterator

            if errorIndication:

                return (
                    None,
                    str(errorIndication),
                )

            if errorStatus:

                return (
                    None,
                    str(errorStatus),
                )

            for varBind in varBinds:

                return (
                    str(varBind[1]),
                    None,
                )

            return (
                None,
                "Unknown SNMP error",
            )

        except Exception as exc:

            return (
                None,
                str(exc),
            )

    async def set(self, oid, value):

        try:

            if isinstance(value, int):

                data = Integer(value)

            else:

                data = OctetString(str(value))

            transport = await UdpTransportTarget.create(
                (self.ip, PORT),
                timeout=self.TIMEOUT,
                retries=self.RETRIES,
            )

            iterator = set_cmd(
                SnmpEngine(),
                CommunityData(
                    COMMUNITY,
                    mpModel=SNMP_VERSION,
                ),
                transport,
                ContextData(),
                ObjectType(
                    ObjectIdentity(oid),
                    data,
                ),
            )

            errorIndication, errorStatus, errorIndex, varBinds = await iterator

            if errorIndication:

                return (
                    False,
                    str(errorIndication),
                )

            if errorStatus:

                return (
                    False,
                    str(errorStatus),
                )

            return (
                True,
                None,
            )

        except Exception as exc:

            return (
                False,
                str(exc),
            )

    def read(self, oid):

        print(f"[SNMP READ] " f"IP={self.ip}, " f"OID={oid}")

        value, error = asyncio.run(self.get(oid))

        print(f"      VALUE = {value}")

        print(f"      ERROR = {error}")

        return (
            value,
            error,
        )

    def write(self, oid, value):

        return asyncio.run(self.set(oid, value))

    def test(self):

        value, error = self.read("1.3.6.1.2.1.1.1.0")

        return error is None


client = SNMPClient()
