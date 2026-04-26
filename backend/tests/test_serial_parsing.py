"""Tests for serial JSON parsing and ESP32 auto-detection."""
import json
import re

import pytest


# The regex lives in serial_reader._read_loop but we can test it directly
ARDUINO_TS_PATTERN = re.compile(r'^\d{2}:\d{2}:\d{2}\.\d{3}\s*->\s*')


def strip_timestamp(line: str) -> str:
    return ARDUINO_TS_PATTERN.sub('', line)


# --- timestamp stripping ---

def test_strips_arduino_ide_timestamp():
    raw = '17:09:47.625 -> {"ts_ms":76336,"distance_cm":99.8}'
    assert strip_timestamp(raw) == '{"ts_ms":76336,"distance_cm":99.8}'


def test_leaves_clean_json_alone():
    raw = '{"ts_ms":76336,"distance_cm":99.8}'
    assert strip_timestamp(raw) == raw


def test_strips_zero_padded_timestamp():
    raw = '00:00:01.000 -> {"ts_ms":1000}'
    assert strip_timestamp(raw) == '{"ts_ms":1000}'


def test_strips_timestamp_with_extra_spaces():
    raw = '12:34:56.789 ->  {"ts_ms":1}'
    # \s* is greedy so both spaces after -> are consumed
    assert strip_timestamp(raw) == '{"ts_ms":1}'


def test_doesnt_strip_non_matching_prefix():
    raw = 'some random text {"ts_ms":1}'
    assert strip_timestamp(raw) == raw


# --- JSON parsing ---

def test_parses_full_esp32_payload():
    payload = '{"ts_ms":76336,"distance_cm":99.8,"temp_c":17.8,"hum_pct":59}'
    data = json.loads(payload)
    assert data['ts_ms'] == 76336
    assert data['distance_cm'] == 99.8
    assert data['temp_c'] == 17.8
    assert data['hum_pct'] == 59


def test_parses_partial_payload():
    # ESP32 might skip fields if sensor read fails
    payload = '{"ts_ms":1000,"distance_cm":50.0}'
    data = json.loads(payload)
    assert 'temp_c' not in data
    assert data['distance_cm'] == 50.0


def test_invalid_json_raises():
    with pytest.raises(json.JSONDecodeError):
        json.loads("not json")


def test_empty_string_raises():
    with pytest.raises(json.JSONDecodeError):
        json.loads("")


# --- ESP32 auto-detection ---

def test_find_esp32_port_detects_cp210x(monkeypatch):
    from app.serial.serial_reader import ESP32SerialReader

    class FakePort:
        device = 'COM3'
        description = 'Silicon Labs CP210x USB to UART Bridge'
        hwid = 'USB VID:PID=10C4:EA60'

    monkeypatch.setattr('serial.tools.list_ports.comports', lambda: [FakePort()])
    assert ESP32SerialReader.find_esp32_port() == 'COM3'


def test_find_esp32_port_detects_ch340(monkeypatch):
    from app.serial.serial_reader import ESP32SerialReader

    class FakePort:
        device = 'COM5'
        description = 'USB-SERIAL CH340'
        hwid = 'USB VID:PID=1A86:7523'

    monkeypatch.setattr('serial.tools.list_ports.comports', lambda: [FakePort()])
    assert ESP32SerialReader.find_esp32_port() == 'COM5'


def test_find_esp32_port_returns_none_with_no_match(monkeypatch):
    from app.serial.serial_reader import ESP32SerialReader

    class FakePort:
        device = 'COM1'
        description = 'Standard Serial Port'
        hwid = 'ACPI\\PNP0501'

    monkeypatch.setattr('serial.tools.list_ports.comports', lambda: [FakePort()])
    assert ESP32SerialReader.find_esp32_port() is None


def test_find_esp32_port_returns_none_with_no_ports(monkeypatch):
    from app.serial.serial_reader import ESP32SerialReader

    monkeypatch.setattr('serial.tools.list_ports.comports', lambda: [])
    assert ESP32SerialReader.find_esp32_port() is None


def test_list_available_ports_format(monkeypatch):
    from app.serial.serial_reader import ESP32SerialReader

    class FakePort:
        device = 'COM3'
        description = 'CP210x'
        hwid = 'USB123'

    monkeypatch.setattr('serial.tools.list_ports.comports', lambda: [FakePort()])
    ports = ESP32SerialReader.list_available_ports()
    assert len(ports) == 1
    assert ports[0] == {'port': 'COM3', 'description': 'CP210x', 'hwid': 'USB123'}
