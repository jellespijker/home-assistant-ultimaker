# UltiMaker for Home Assistant

A Home Assistant integration that monitors and controls UltiMaker printers, reaching them over the local network, through UltiMaker Digital Factory, or both.

## Language

### Printers and connections

**Printer**:
One physical UltiMaker machine, shown in Home Assistant as one device regardless of how many connections reach it.
_Avoid_: Cluster, host, machine

**LAN connection**:
A link to a single printer over the local network, giving live telemetry.
_Avoid_: Local entry, IP connection

**Cloud connection**:
A link to one Digital Factory account, giving access to every printer in that account.
_Avoid_: Cloud entry, DF connection, account entry

**Merged printer**:
A printer reached by both a LAN connection and a cloud connection, presented as a single device.
_Avoid_: Dual printer, linked printer

**Cloud-only printer**:
A printer reached by a cloud connection and no LAN connection.

**LAN-only printer**:
A printer reached by a LAN connection and no cloud connection.

### Digital Factory

**Digital Factory**:
UltiMaker's cloud platform for managing printers, print jobs and projects remotely.
_Avoid_: UltiMaker Cloud, DF, Connect

**API token**:
A long-lived credential created by a workspace admin in Digital Factory, available only on some subscription plans.
_Avoid_: API key, access key

**Workspace**:
The organisation a Digital Factory account acts in; it holds the subscription plan and the printers.
_Avoid_: Organization, team

**Printer cap**:
The maximum number of printers a workspace's subscription plan allows in Digital Factory.
_Avoid_: Printer limit, quota

**Print queue**:
The ordered list of print jobs waiting to run on a printer, held by Digital Factory.

**Upsell**:
A one-time, dismissible prompt suggesting a Digital Factory subscription upgrade when the account's printer cap keeps LAN printers out of the cloud.
