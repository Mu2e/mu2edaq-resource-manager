"""Tests for the ports: ANY config designation (all ports)."""

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load_resource_manager():
    # resource_manager imports models by name, so make server/ importable.
    import sys
    sys.path.insert(0, str(ROOT / "server"))
    spec = importlib.util.spec_from_file_location(
        "resource_manager", ROOT / "server" / "resource_manager.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rm_mod = _load_resource_manager()
ResourceManager = rm_mod.ResourceManager

CONFIG = """\
resources:
  - class: DTC
    name: DTC
    enumerator: "01"
    location:
      node: node01
      user: daq
      ports: ANY
  - class: CFO
    name: CFO
    enumerator: "01"
    location:
      node: node02
      user: daq
      ports: [3000, 3001]
"""


def _manager(tmp_path):
    cfg = tmp_path / "resources.yaml"
    cfg.write_text(CONFIG)
    return ResourceManager(str(cfg))


def test_any_sets_ports_any_flag(tmp_path):
    rm = _manager(tmp_path)
    res = rm.get_resource("DTC", "DTC", "01")
    assert res.location.ports_any is True
    assert res.location.ports == []


def test_explicit_ports_not_any(tmp_path):
    rm = _manager(tmp_path)
    res = rm.get_resource("CFO", "CFO", "01")
    assert res.location.ports_any is False
    assert res.location.ports == [3000, 3001]


def test_parse_ports_helper():
    assert ResourceManager._parse_ports("ANY") == ([], True)
    assert ResourceManager._parse_ports("any") == ([], True)
    assert ResourceManager._parse_ports([2000, 2001]) == ([2000, 2001], False)
    assert ResourceManager._parse_ports(["ANY", 2000]) == ([2000], True)
    assert ResourceManager._parse_ports([]) == ([], False)
