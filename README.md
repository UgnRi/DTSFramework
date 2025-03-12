# Teltonika Router Test Framework

This framework provides automated testing capabilities for Teltonika routers, focusing on the MQTT Broker and Data to Server functionalities.

## Overview

The Teltonika Router Test Framework allows you to automate configuration and validation of various router features using different test methods:

- **SSH Tests**: Configure the router via SSH commands
- **API Tests**: Configure the router via its REST API
- **GUI Tests**: Configure the router through the web interface using browser automation
- **Validation**: Verify configurations and functionality across all test methods

## Requirements

- Python 3.8+
- Playwright (for GUI tests)
- Required Python packages (install using `pip install -r requirements.txt`)

## Installation
    
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Install Playwright: `playwright install firefox`

## Configuration

The framework uses configuration files to specify device and test parameters:

### Device Configuration

Create a device configuration file (default: `config/device_config.json`) with the router connection details:

```json
{
  "device": {
    "name": "Router Model",
    "ip": "192.168.1.1",
    "username": "admin",
    "password": "admin",
    "modem": "model",
    "firmware": "version"
  },
  "ssh": {
    "port": 22
  },
  "api": {
    "port": 80
  }
}
```

### Test Scenarios

Create test scenarios in the `config/test_scenarios` directory. Each scenario should be a JSON file with specific configuration options:

#### Data to Server Scenario Example

```json
{
  "scenario_name": "data_to_server",
  "description": "Data to Server configuration test",
  "config": {
    "instanceName": "test_instance",
    "data_config": {
      "name": "input",
      "type": "MQTT",
      "type_settings": {
        "server_address": "mqtt.example.com",
        "port": 1883,
        "topic": "test/topic",
        "client_id": 1,
        "QoS": 1
      },
      "format_type": "JSON",
      "values": ["data", "topic", "retain"]
    },
    "collection_config": {
      "period": 5,
      "retry": true
    },
    "server_config": {
      "server_address": "mqtt.example.com",
      "port": 1883,
      "topic": "test/topic",
      "client_id": "client_id",
      "QoS": 1
    }
  }
}
```

## Usage

Run the framework with specific test types and scenarios:

```bash
python run.py --test-type <test_type> --mqtt-scenario <mqtt_scenario> --dts-scenario <dts_scenario>
```

### Parameters

- `--test-type`: Type of tests to run (`ssh`, `api`, `gui`, or `all`)
- `--mqtt-scenario`: MQTT Broker scenario name (without .json extension)
- `--dts-scenario`: Data to Server scenario name (without .json extension)
- `--config`: Path to device configuration file (default: `config/device_config.json`)
- `--scenario-dir`: Directory containing scenario files (default: `config/test_scenarios`)

### Examples

Run SSH tests for Data to Server:
```bash
python run.py --test-type ssh --dts-scenario dts
```

Run all tests for both MQTT Broker and Data to Server:
```bash
python run.py --test-type all --mqtt-scenario mqtt --dts-scenario dts
```

## Architecture

The framework uses a modular architecture:

- `src/main.py`: Main entry point for running tests
- `src/test_scenarios/`: Contains test implementations for each feature
  - `mqtt_broker/`: MQTT Broker tests
  - `data_to_server/`: Data to Server tests
- `src/backend/`: Backend utilities and API clients
- `src/utils/`: Utility functions for logging, results, etc.

## Test Results

Results are saved in CSV format with:
- Test scenario name
- Status (PASS/FAIL)
- Details of the test run

The filename includes device information and timestamp.

## Development

### Adding New Tests

To add a new test scenario:

1. Create a new scenario JSON file in `config/test_scenarios/`
2. Implement test classes in `src/test_scenarios/`
3. Update the main runner to detect and execute your tests

### Custom Test Implementations

Each feature supports three test types:

1. **SSH Test**: Implement a class derived from `BaseSSHTest`
2. **API Test**: Implement a class derived from `BaseAPITest`
3. **GUI Test**: Implement a class with setup, execute, and cleanup methods

## Data to Server Configuration

The Data to Server functionality supports various input types:

- Base
- MQTT
- Mobile usage
- Impulse counter
- Modbus
- Modbus alarms
- WiFi scanner
- Bluetooth
- GSM
- MNF info
- Lua script

Each input type has specific configuration options defined in the scenario file.