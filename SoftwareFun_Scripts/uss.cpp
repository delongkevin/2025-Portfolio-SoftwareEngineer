// --- Configuration Constants ---
const int NUM_SENSORS = 12;
const int NUM_RELAYS = 12; // Assuming one relay per sensor to power/enable it

// IMPORTANT: Define your sensor input pins and relay control pins here.
const int sensorSignalPins[NUM_SENSORS] = {2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13}; // Pins to READ sensor data
const int relayControlPins[NUM_RELAYS] = {A0, A1, A2, A3, A4, A5, 22, 23, 24, 25, 26, 27}; // Pins to CONTROL relays (connected to relay module IN pins)

// Timing settings
const unsigned long SENSOR_POWER_ON_DURATION = 1000; // ms: How long to keep a sensor powered via its relay to take a reading.
const unsigned long SENSOR_READ_CYCLE_INTERVAL = 5000; // ms: How often to start a cycle of powering and reading the next sensor.
const unsigned long SENSOR_STABILIZATION_DELAY = 100; // ms: Brief delay after powering sensor before reading.

const bool IS_RELAY_ACTIVE_HIGH = true;      // Set to 'true' if HIGH turns relay ON, 'false' if LOW turns relay ON

// --- Global Variables ---
int currentSensorIndex = 0;                 // Which sensor we are currently processing
unsigned long lastCycleStartTime = 0;       // When the last sensor power-on cycle began
unsigned long currentRelayOffTime = 0;      // When the currently active relay should be turned off
bool isRelayCurrentlyActive = false;        // Flag to indicate if any relay is active in the power-on cycle
int activeRelayIndex = -1;                  // Index of the relay/sensor currently powered

void setup() {
  Serial.begin(9600);
  while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
  }
  Serial.println("Sensor Power & Read System Initializing...");
  Serial.println("----------------------------------------------------------");
  Serial.println("WARNING: This code assumes 12 sensor inputs and 12 relay outputs.");
  Serial.println("An Arduino Uno R3 does NOT have enough pins (20 digital I/O) for this (24 needed).");
  Serial.println("Consider an Arduino Mega or I/O expanders.");
  Serial.println("----------------------------------------------------------");


  // Initialize sensor signal pins as INPUT
  for (int i = 0; i < NUM_SENSORS; i++) {
    pinMode(sensorSignalPins[i], INPUT);
    // If your sensors are 0V/3.3V and need a pull-up for the HIGH state (e.g. open-drain output)
    // and if HIGH means 'not detected' and LOW means 'detected', you might use INPUT_PULLUP.
    // For a sensor that actively outputs 0V or 3.3V, INPUT is usually fine.
  }

  // Initialize relay control pins as OUTPUT and ensure all relays are OFF initially
  for (int i = 0; i < NUM_RELAYS; i++) {
    pinMode(relayControlPins[i], OUTPUT);
    if (IS_RELAY_ACTIVE_HIGH) {
      digitalWrite(relayControlPins[i], LOW); // Turn OFF
    } else {
      digitalWrite(relayControlPins[i], HIGH); // Turn OFF
    }
  }
  Serial.println("Initialization Complete.");
}

void loop() {
  unsigned long currentTime = millis();

  // --- Manage currently active relay/sensor ---
  if (isRelayCurrentlyActive && activeRelayIndex != -1) {
    // Check if it's time to turn off the currently active relay
    if (currentTime >= currentRelayOffTime) {
      Serial.print(currentTime);
      Serial.print("ms: Turning OFF relay for sensor ");
      Serial.println(activeRelayIndex);
      if (IS_RELAY_ACTIVE_HIGH) {
        digitalWrite(relayControlPins[activeRelayIndex], LOW); // Turn relay OFF
      } else {
        digitalWrite(relayControlPins[activeRelayIndex], HIGH); // Turn relay OFF
      }
      isRelayCurrentlyActive = false;
      activeRelayIndex = -1;
    }
  }

  // --- Start a new sensor power-on and read cycle ---
  if (!isRelayCurrentlyActive && (currentTime - lastCycleStartTime >= SENSOR_READ_CYCLE_INTERVAL)) {
    lastCycleStartTime = currentTime;

    Serial.print(currentTime);
    Serial.print("ms: Starting cycle for sensor ");
    Serial.println(currentSensorIndex);

    // 1. Turn ON the relay for the current sensor
    activeRelayIndex = currentSensorIndex; // Store which relay is now active
    Serial.print(currentTime);
    Serial.print("ms: Turning ON relay for sensor ");
    Serial.println(activeRelayIndex);
    if (IS_RELAY_ACTIVE_HIGH) {
      digitalWrite(relayControlPins[activeRelayIndex], HIGH); // Turn relay ON
    } else {
      digitalWrite(relayControlPins[activeRelayIndex], LOW);  // Turn relay ON
    }
    isRelayCurrentlyActive = true;
    currentRelayOffTime = currentTime + SENSOR_POWER_ON_DURATION;

    // 2. Wait for sensor stabilization (non-blocking preferred, but simple delay for example)
    // For a non-blocking wait, you'd set a state and check millis() again.
    // Here, a small blocking delay is used for simplicity.
    // This delay happens *after* the relay is on but before reading.
    // The SENSOR_POWER_ON_DURATION should be longer than this stabilization delay.
    delay(SENSOR_STABILIZATION_DELAY); // Blocking delay - use with caution

    // 3. Read the sensor value
    int sensorValue = digitalRead(sensorSignalPins[activeRelayIndex]);
    Serial.print(millis()); // Show time of actual read
    Serial.print("ms: Sensor ");
    Serial.print(activeRelayIndex);
    Serial.print(" (Pin D");
    Serial.print(sensorSignalPins[activeRelayIndex]);
    Serial.print=") Value: ");
    Serial.println(sensorValue == HIGH ? "HIGH (3.3V)" : "LOW (0V)");

    // (Optional: Do something with sensorValue here)

    // 4. The relay will be turned off by the management section above when currentRelayOffTime is reached.

    // Move to the next sensor for the next cycle
    currentSensorIndex++;
    if (currentSensorIndex >= NUM_SENSORS) {
      currentSensorIndex = 0; // Wrap around
    }
  }
}