# Development Guidelines for Home Assistant Ultimaker Integration

This document provides guidelines and information for developers working on the Home Assistant Ultimaker integration.

## Build/Configuration Instructions

### Development Environment Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/jellespijker/home-assistant-ultimaker.git
   cd home-assistant-ultimaker
   ```

2. **Dependencies**:
   The integration has no external Python package dependencies beyond what's provided by Home Assistant. However, for development and testing, you'll need:
   ```bash
   pip install pytest pytest-asyncio aiohttp homeassistant
   ```

3. **Installation for Development**:
   - For development, you can create a symbolic link from your development directory to your Home Assistant custom_components directory:
     ```bash
     ln -s /path/to/home-assistant-ultimaker/custom_components/ultimaker /path/to/homeassistant/custom_components/
     ```
   - Alternatively, copy the `custom_components/ultimaker` directory to your Home Assistant `custom_components` directory.

4. **Configuration**:
   Add the following to your Home Assistant `configuration.yaml`:
   ```yaml
   sensor:
     - platform: ultimaker
       name: your_printer_name
       host: your_printer_ip
       scan_interval: 10  # optional, default 10
       decimal: 2  # optional, default 2
       sensors:
         - status
         - state
         - progress
         # Add other sensors as needed
   ```

## Testing Information

### Running Tests

1. **Install Testing Dependencies**:
   ```bash
   pip install pytest pytest-asyncio aiohttp homeassistant
   ```

2. **Run All Tests**:
   ```bash
   pytest tests/
   ```

3. **Run Specific Tests**:
   ```bash
   pytest tests/test_sensor.py
   ```

4. **Run with Verbose Output**:
   ```bash
   pytest -xvs tests/
   ```

### Adding New Tests

1. **Test Structure**:
   - Place test files in the `tests/` directory
   - Name test files with the prefix `test_`
   - Name test functions with the prefix `test_`

2. **Mocking External Services**:
   - Use `unittest.mock` or `pytest-mock` to mock external services
   - Create fixtures for commonly used mocks (see `tests/test_sensor.py` for examples)

3. **Example Test**:
   The repository includes an example test in `tests/test_sensor.py` that demonstrates:
   - How to mock the Ultimaker API responses
   - How to test sensor creation and updates
   - How to verify sensor states

4. **Running the Example Test**:
   ```bash
   python tests/run_example_test.py
   ```

## Code Style and Development Guidelines

1. **Code Style**:
   - Follow the [Home Assistant Python Style Guide](https://developers.home-assistant.io/docs/development_guidelines)
   - Use type hints for function parameters and return values
   - Document classes and methods with docstrings

2. **Integration Structure**:
   - `__init__.py`: Contains the setup function for the integration
   - `sensor.py`: Implements the sensor platform
   - `manifest.json`: Defines integration metadata

3. **API Communication**:
   - The integration communicates with the Ultimaker printer's API at `http://<printer_ip>/api/v1/`
   - API endpoints used:
     - `/printer`: For printer status and hardware information
     - `/print_job`: For print job state and progress
     - `/system`: For system information

4. **Error Handling**:
   - The integration includes error handling for network issues and API errors
   - If the printer is offline, the status sensor will show "not connected"

5. **Throttling**:
   - API calls are throttled to avoid overloading the printer
   - The default scan interval is 10 seconds, configurable via `scan_interval`

## Debugging

1. **Enable Debug Logging**:
   Add the following to your Home Assistant `configuration.yaml`:
   ```yaml
   logger:
     default: info
     logs:
       custom_components.ultimaker: debug
   ```

2. **Common Issues**:
   - **Connection Issues**: Verify the printer IP address and that the printer is online
   - **Sensor Not Updating**: Check the scan_interval setting and verify API access

3. **Testing API Directly**:
   You can test the Ultimaker API directly using curl:
   ```bash
   curl http://<printer_ip>/api/v1/printer
   curl http://<printer_ip>/api/v1/print_job
   curl http://<printer_ip>/api/v1/system
   ```

## Versioning and Releases

1. **Version Numbering**:
   - The integration follows semantic versioning (MAJOR.MINOR.PATCH)
   - Update the version in `manifest.json` when making changes

2. **Release Process**:
   - Tag releases in git with the version number
   - Update the HACS repository when releasing new versions