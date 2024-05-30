#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

# Example output from agent:
# <<<mknotifyd:sep(0)>>>
# 1571151364
# [heute]
# Version:         2019.10.14
# Updated:         1571151346 (2019-10-15 16:55:46)
# Started:         1571143926 (2019-10-15 14:52:06, 7420 sec ago)
# Configuration:   1571143926 (2019-10-15 14:52:06, 7420 sec ago)
# Listening FD:    5
#
# Spool:           New
# Count:           0
# Oldest:
# Youngest:
#
# Spool:           Deferred
# Count:           0
# Oldest:
# Youngest:
#
# Spool:           Corrupted
# Count:           0
# Oldest:
# Youngest:
#
# Queue:           mail
# Waiting:         0
# Processing:      0
#
# Queue:           None
# Waiting:         0
# Processing:      0
#
# Connection:               127.0.0.1:49850
# Type:                     incoming
# State:                    established
# Since:                    1571143941 (2019-10-15 14:52:21, 7405 sec ago)
# Notifications Sent:       41
# Notifications Received:   41
# Pending Acknowledgements:
# Socket FD:                6
# HB. Interval:             10 sec
# LastIncomingData:         1571149829 (2019-10-15 16:30:29, 1517 sec ago)
# LastHeartbeat:            1571151344 (2019-10-15 16:55:44, 2 sec ago)
# InputBuffer:              0 Bytes
# OutputBuffer:             0 Bytes

from collections.abc import Mapping
from typing import Any

from cmk.base.check_api import LegacyCheckDefinition
from cmk.base.config import check_info

from cmk.agent_based.v2 import render, StringTable

Section = Mapping[str, object]


def parse_mknotifyd(  # pylint: disable=too-many-branches
    string_table: StringTable,
) -> Section:
    timestamp, data = float(string_table[0][0]), string_table[1:]

    parsed: dict[str, Any] = {
        "sites": {},
        "timestamp": timestamp,
    }

    for line in data:
        if line[0].startswith("["):
            site = line[0][1:-1]
            site_entry: dict[str, dict] = {
                "spools": {},
                "connections": {},
                "queues": {},
            }
            sub_entry = site_entry
            parsed["sites"][site] = site_entry
        elif ":" in line[0]:
            varname, value = line[0].split(":", 1)

            if varname == "Encryption":
                continue
            value = value.strip()

            if varname == "Site":
                connected_site = value.split(" (")[0]
            elif varname == "Spool":
                sub_entry = {}
                site_entry["spools"][value] = sub_entry

            elif varname == "Connection":
                sub_entry = {}
                # for "mknotifyd.connection_v2"
                site_entry["connections"][connected_site] = sub_entry
                # keep the "mknotifyd.connection" services working
                site_entry["connections"][value] = sub_entry

            elif varname == "Queue":
                sub_entry = {}
                site_entry["queues"][value] = sub_entry

            else:
                sub_entry_value: Any = value
                if value == "None":
                    sub_entry_value = None
                elif value and varname == "Listening FD":
                    # May be the listening FD number or an error message
                    try:
                        sub_entry_value = int(value.split()[0])
                    except ValueError:
                        pass
                elif (
                    value
                    and value != "-"
                    and varname
                    not in [
                        "Type",
                        "State",
                        "Version",
                        "Status Message",
                        "Pending Acknowledgements",
                        "Connect Time",
                    ]
                ):
                    sub_entry_value = int(value.split()[0])
                elif varname == "Connect Time":
                    sub_entry_value = float(value.split()[0])
                sub_entry[varname] = sub_entry_value

    # Fixup names of the connections. For incoming connections the remote
    # port is irrelevant. It changes randomly. But there might anyway be
    # more than one connection from the same remote host, so we are forced
    # to create artificial numbers if that is the case
    for stats in parsed["sites"].values():
        remote_addresses: dict = {}
        for connection_name, connection in list(stats["connections"].items()):
            if connection["Type"] == "incoming":
                remote_address_site = connection_name.split(":")[0]
                remote_addresses.setdefault(remote_address_site, []).append(connection)
                del stats["connections"][connection_name]

        for address, connections in remote_addresses.items():
            if len(connections) == 1:
                stats["connections"][address] = connections[0]
            else:
                for nr, connection in enumerate(connections):
                    stats["connections"][address + "/" + str(nr + 1)] = connection

    return parsed


#   .--Spooler Status------------------------------------------------------.
#   | ____                    _             ____  _        _               |
#   |/ ___| _ __   ___   ___ | | ___ _ __  / ___|| |_ __ _| |_ _   _ ___   |
#   |\___ \| '_ \ / _ \ / _ \| |/ _ \ '__| \___ \| __/ _` | __| | | / __|  |
#   | ___) | |_) | (_) | (_) | |  __/ |     ___) | || (_| | |_| |_| \__ \  |
#   ||____/| .__/ \___/ \___/|_|\___|_|    |____/ \__\__,_|\__|\__,_|___/  |
#   |      |_|                                                             |
#   +----------------------------------------------------------------------+
#   |                                                                      |
#   '----------------------------------------------------------------------'


def inventory_mknotifyd(parsed):
    return [(p, {}) for p in parsed["sites"]]


def check_mknotifyd(item, _no_params, parsed):
    if (stat := parsed["sites"].get(item)) is None:
        return

    # There are dummy-entries created during the parsing. So the
    # dict will never be completely empty. We check for Version
    # because this should be always present in a valid state file.
    if (version := stat.get("Version")) is None:
        yield 2, "The state file seems to be empty or corrupted. It is very likely that the spooler is not working properly"
        return
    yield 0, f"Version: {version}", []

    # Check age of status file. It's updated every 20 seconds
    status_age = parsed["timestamp"] - stat["Updated"]
    if status_age > 90:
        state = 2
        infotext = (
            f"Status last updated {render.timespan(status_age)} ago, spooler seems crashed or busy"
        )
    else:
        state = 0
        infotext = "Spooler running"
    yield state, infotext, [
        ("last_updated", status_age),
        ("new_files", stat["spools"]["New"]["Count"]),
    ]

    corrupted = stat["spools"]["Corrupted"]
    if corrupted.get("Count"):
        age = parsed["timestamp"] - corrupted["Youngest"]
        perf_data = [("corrupted_files", corrupted["Count"])]
        yield 1, f"{corrupted['Count']} corrupted files: youngest {render.timespan(age)} ago", perf_data

    # Are there deferred files that are too old?
    deferred = stat["spools"]["Deferred"]
    if deferred.get("Count"):
        age = parsed["timestamp"] - deferred["Oldest"]
        count = deferred["Count"]
        perf_data = [("deferred_age", age), ("deferred_files", deferred["Count"])]
        if age > 5:
            state = 1
        elif age > 600:  # TODO: not reachable
            state = 2
        else:
            state = 0
        yield state, f"{count} deferred files: oldest {render.timespan(age)} ago", perf_data


check_info["mknotifyd"] = LegacyCheckDefinition(
    parse_function=parse_mknotifyd,
    service_name="OMD %s Notification Spooler",
    discovery_function=inventory_mknotifyd,
    check_function=check_mknotifyd,
)

#   .--Connections---------------------------------------------------------.
#   |        ____                            _   _                         |
#   |       / ___|___  _ __  _ __   ___  ___| |_(_) ___  _ __  ___         |
#   |      | |   / _ \| '_ \| '_ \ / _ \/ __| __| |/ _ \| '_ \/ __|        |
#   |      | |__| (_) | | | | | | |  __/ (__| |_| | (_) | | | \__ \        |
#   |       \____\___/|_| |_|_| |_|\___|\___|\__|_|\___/|_| |_|___/        |
#   |                                                                      |
#   '----------------------------------------------------------------------'


def inventory_mknotifyd_connection(parsed):
    # deprecated, do not discover anything
    return
    yield


_V2_SERVICE_NAMING = "Notification Spooler connection to"


def check_mknotifyd_connection(item, _no_params, parsed):

    # "mknotifyd.connection_v2"
    if _V2_SERVICE_NAMING in item:
        site_name, connection_name = item.split(f" {_V2_SERVICE_NAMING} ", 1)
    # "mknotifyd.connection"
    else:
        site_name, connection_name = item.split("-", 1)

    if site_name not in parsed["sites"]:
        return

    states = {
        "established": (0, "Alive"),
        "cooldown": (2, "Connection failed or terminated"),
        "initial": (1, "Initialized"),
        "connecting": (2, "Trying to connect"),
    }

    if (connection := parsed["sites"][site_name]["connections"].get(connection_name)) is not None:

        yield states[connection["State"]]

        if "Status Message" in connection:
            yield 0, connection["Status Message"]

        if connection["State"] == "established":
            age = parsed["timestamp"] - connection["Since"]
            yield 0, f"Uptime: {render.timespan(age)}"

            if "Connect Time" in connection:
                yield 0, f"Connect time: {connection['Connect Time']:.3f} sec"

        for what in ("Sent", "Received"):
            if num := connection["Notifications " + what]:
                yield 0, f"{num} Notifications {what.lower()}"


# deprecated
check_info["mknotifyd.connection"] = LegacyCheckDefinition(
    service_name="OMD %s Notify Connection",
    sections=["mknotifyd"],
    discovery_function=inventory_mknotifyd_connection,
    check_function=check_mknotifyd_connection,
)


def inventory_mknotifyd_connection_v2(parsed):
    for site_name, stats in parsed["sites"].items():
        for connection_name in stats["connections"]:
            if "." in connection_name:
                # item of old discovered "mknotifyd.connection"
                continue
            yield f"{site_name} {_V2_SERVICE_NAMING} {connection_name}", {}


check_info["mknotifyd.connection_v2"] = LegacyCheckDefinition(
    service_name="OMD %s",
    sections=["mknotifyd"],
    discovery_function=inventory_mknotifyd_connection_v2,
    check_function=check_mknotifyd_connection,
)
