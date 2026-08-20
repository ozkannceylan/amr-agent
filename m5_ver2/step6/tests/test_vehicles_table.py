"""The VEHICLES table and the per-vehicle contract."""
import pytest

import status_contract as sc


def test_table_has_exactly_the_two_vehicles_with_disjoint_ports():
    assert set(sc.VEHICLES) == {"f1", "f2"}
    ports = [v[k] for v in sc.VEHICLES.values()
             for k in ("plc_port", "sensor_port")]
    assert len(ports) == len(set(ports))
    assert 5100 not in ports and 5101 not in ports   # step5's family


def test_contract_namespaces_every_ros_name():
    c = sc.contract("f2")
    assert c["status_topic"] == "/f2/plc/status"
    assert c["fields_topic"] == "/f2/safety/fields"
    assert c["encoders_topic"] == "/f2/safety/encoders"
    assert c["scan_topic"].format("back") == \
        "/f2/gz/safety_scanner_back/measurement"
    assert c["vehicle_cmd_topic"] == "/f2/vehicle/cmd_vel"
    assert c["hmi_cmd_topic"] == "/f2/hmi/cmd_vel"
    assert c["plc_port"] == 5120 and c["sensor_port"] == 5121


def test_module_constants_follow_the_env_vehicle():
    # conftest sets VEHICLE=f1 for the whole suite.
    assert sc.VID == "f1"
    assert sc.STATUS_TOPIC == "/f1/plc/status"
    assert sc.PLC_PORT == 5110 and sc.SENSOR_PORT == 5111
    assert sc.CONFIG_PATH.replace("\\", "/").endswith(
        "step6/vehicles/f1/config.yaml")


def test_unknown_vehicle_refused():
    with pytest.raises(SystemExit):
        sc.contract("f9")


def test_env_free_from_import_reads_the_table():
    # The launch file (both vehicles from one process) and
    # tools/instantiate_vehicle.py import this module with no VEHICLE.
    # A subprocess because conftest sets VEHICLE for the whole suite,
    # which takes the guarded branch and hides the else branch entirely.
    import os
    import subprocess
    import sys

    env = {k: v for k, v in os.environ.items() if k != "VEHICLE"}
    ipc = os.path.dirname(os.path.abspath(sc.__file__))
    src = (
        "import sys; sys.path.insert(0, {!r});"
        "from status_contract import VEHICLES, contract;"
        "print(sorted(VEHICLES), contract('f2')['status_topic'])"
    ).format(ipc)
    done = subprocess.run([sys.executable, "-c", src], env=env,
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "['f1', 'f2'] /f2/plc/status"


def test_env_free_per_vehicle_constant_still_refused():
    import os
    import subprocess
    import sys

    env = {k: v for k, v in os.environ.items() if k != "VEHICLE"}
    ipc = os.path.dirname(os.path.abspath(sc.__file__))
    src = (
        "import sys; sys.path.insert(0, {!r});"
        "import status_contract; status_contract.STATUS_TOPIC"
    ).format(ipc)
    done = subprocess.run([sys.executable, "-c", src], env=env,
                          capture_output=True, text=True)
    assert done.returncode != 0
    assert "env VEHICLE is not set" in done.stderr
    assert "STATUS_TOPIC" in done.stderr
