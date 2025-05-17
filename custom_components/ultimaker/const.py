"""Constants for the Ultimaker integration."""

DOMAIN = "ultimaker"

# Configuration
CONF_API_TYPE = "api_type"
CONF_HOST = "host"
CONF_CLUSTER_ID = "cluster_id"
CONF_DECIMAL = "decimal"
CONF_ORGANIZATION_ID = "organization_id"

# API Types
API_TYPE_LOCAL = "local"
API_TYPE_CLOUD = "cloud"

# OAuth2
OAUTH2_AUTHORIZE = "https://account.ultimaker.com/authorize"
OAUTH2_TOKEN = "https://account.ultimaker.com/token"
OAUTH2_JWKS = "https://account.ultimaker.com/.well-known/jwks"
USER_INFO_URL = "https://api.ultimaker.com/connect/v1/users/current"

# API URLs
LOCAL_API_URL = "http://{0}/api/v1"
CLOUD_API_URL = "https://api.ultimaker.com/connect/v1"

# Default values
DEFAULT_SCAN_INTERVAL_LOCAL = 10
DEFAULT_SCAN_INTERVAL_CLOUD = 30
DEFAULT_DECIMAL = 2

# Sensor types
SENSOR_STATUS = "status"
SENSOR_STATE = "state"
SENSOR_PROGRESS = "progress"
SENSOR_BED_TEMPERATURE = "bed_temperature"
SENSOR_BED_TEMPERATURE_TARGET = "bed_temperature_target"
SENSOR_BED_TYPE = "bed_type"
SENSOR_HOTEND_1_TEMPERATURE = "hotend_1_temperature"
SENSOR_HOTEND_1_TEMPERATURE_TARGET = "hotend_1_temperature_target"
SENSOR_HOTEND_1_ID = "hotend_1_id"
SENSOR_HOTEND_2_TEMPERATURE = "hotend_2_temperature"
SENSOR_HOTEND_2_TEMPERATURE_TARGET = "hotend_2_temperature_target"
SENSOR_HOTEND_2_ID = "hotend_2_id"

# Cloud-specific sensor types
SENSOR_CLUSTER_STATUS = "cluster_status"
SENSOR_PRINTER_COUNT = "printer_count"
SENSOR_MAINTENANCE_REQUIRED = "maintenance_required"
SENSOR_MATERIAL_REMAINING = "material_remaining"

# Hotend material sensors
SENSOR_HOTEND_1_MATERIAL_EXTRUDED = "hotend_1_material_extruded"
SENSOR_HOTEND_1_MATERIAL_REMAINING = "hotend_1_material_remaining"
SENSOR_HOTEND_1_MATERIAL_TYPE = "hotend_1_material_type"
SENSOR_HOTEND_2_MATERIAL_EXTRUDED = "hotend_2_material_extruded"
SENSOR_HOTEND_2_MATERIAL_REMAINING = "hotend_2_material_remaining"
SENSOR_HOTEND_2_MATERIAL_TYPE = "hotend_2_material_type"

# Print job time sensors
SENSOR_PRINT_JOB_TIME_TOTAL = "print_job_time_total"
SENSOR_PRINT_JOB_TIME_ELAPSED = "print_job_time_elapsed"
SENSOR_PRINT_JOB_TIME_REMAINING = "print_job_time_remaining"
