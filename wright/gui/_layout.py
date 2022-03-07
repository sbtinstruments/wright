import json
from datetime import datetime
from typing import Any

import PySimpleGUI as sg

from ..commands import RESET_DEVICE_STATUS_MAP
from ..config.branding import Branding
from ..device import DeviceType
from ._config import GUI_CONFIG_PATH


def create_layout() -> list[Any]:
    """Return layout for the GUI."""
    sg.theme("SystemDefaultForReal")

    try:
        with GUI_CONFIG_PATH.open("r") as io:
            defaults = json.load(io)
    except (OSError, json.JSONDecodeError):
        defaults = {}

    swu_layout = [
        [
            sg.Input(
                key="swu_file", default_text=defaults.get("swu_file"), size=(20, None)
            ),
            sg.FileBrowse(file_types=(("SWUpdate files", "*.swu"),)),
        ],
    ]

    device_layout = [
        [
            sg.Combo(
                key="device_type",
                values=[dt.name for dt in DeviceType],
                default_value=defaults.get("device_type"),
                size=(30, None),
            ),
        ]
    ]

    device_version_layout = [
        [
            sg.Input(
                key="device_version",
                default_text=defaults.get("device_version"),
                size=(30, None),
            ),
        ],
    ]

    branding_layout = [
        [
            sg.Combo(
                key="branding",
                values=[brand.name for brand in Branding],
                default_value=defaults.get("branding"),
                size=(30, None),
            ),
        ],
    ]

    now = datetime.now()
    now_iso = now.isocalendar()
    hostname_layout = [
        [
            sg.Input(
                key="hostname_device_abbr",
                size=(2, None),
                disabled=True,
                pad=((5, 0), (3, 3)),
            ),
            sg.Input(
                key="hostname_year",
                default_text=str(now_iso[0])[2:],
                size=(2, None),
                pad=(0, 0),
            ),
            sg.Input(
                key="hostname_week",
                default_text=now_iso[1],
                size=(2, None),
                pad=(0, 0),
            ),
            sg.Input(
                key="hostname_id",
                default_text=defaults.get("hostname_id"),
                size=(3, None),
                pad=((0, 5), (3, 3)),
            ),
        ],
        [sg.Text("Previous runs:", pad=((5, 5), (3, 0)))],
        [
            sg.Multiline(
                key="command_log",
                size=(26, 18),
                font=("Monospace", 10),
                disabled=True,
                pad=((5, 5), (0, 3)),
            ),
        ],
    ]

    left_column_layout = [
        [sg.Frame("SWUpdate file", swu_layout)],
        [sg.Frame("Device", device_layout)],
        [sg.Frame("Device version", device_version_layout)],
        [sg.Frame("Branding", branding_layout)],
        [sg.Frame("Hostname", hostname_layout)],
        [
            sg.Button(
                "Start",
                key="submit",
                tooltip="Hotkey: ENTER",
                bind_return_key=True,
                size=(30, None),
            )
        ],
    ]

    steps_layout = []
    for name in RESET_DEVICE_STATUS_MAP:
        title = name.replace("_", " ").capitalize()
        disabled = name == "prepare"
        steps_layout.append(
            [
                sg.Checkbox(
                    title,
                    disabled=disabled,
                    default=defaults.get(f"{name}_enabled", True),
                    key=f"{name}_enabled",
                    size=(15, 1),
                ),
                sg.Text("Max tries", size=(8, 1)),
                sg.Spin(
                    list(range(1, 11)),
                    initial_value=defaults.get(f"{name}max_tries", 10),
                    disabled=disabled,
                    key=f"{name}_max_tries",
                ),
                sg.ProgressBar(
                    max_value=100,
                    key=name,
                    size=(40, 10),
                    relief=sg.RELIEF_SUNKEN,
                    border_width=1,
                ),
                sg.StatusBar("", key=f"{name}_status", size=(35, 1)),
            ]
        )

    right_column_layout = [
        [
            sg.Multiline(
                key="output",
                size=(160, 30),
                font=("Monospace", 8),
                disabled=True,
            )
        ],
        [sg.Frame("Steps", steps_layout)],
    ]

    # All the stuff inside your window.
    return [
        [
            sg.Column(left_column_layout, vertical_alignment="top"),
            sg.Column(right_column_layout, vertical_alignment="top"),
        ],
    ]
