#include <SPI.h>
#include <mcp_can.h>
#include "sbus.h"
#include <Wire.h>
#include <Adafruit_MCP4725.h>

// ---------------- Pins ----------------
#define SPI_CS_PIN   5     // MCP2515 CS
#define SBUS_RX_PIN  17    // SBUS signal from the receiver
#define SBUS_TX_PIN  -1    // not used
#define RELAY_PIN    25    // relay IN  (GPIO24 does not exist on a classic ESP32)
#define I2C_SDA      21
#define I2C_SCL      22

// ---------------- Tuning constants (calibrate here) ----------------
const int   CH_RIGHT_END = 172;     // CH2 value at full right
const int   CH_LEFT_END  = 1811;    // CH2 value at full left
const int   CH_DEAD_MIN  = 985;     // steering dead-zone lower bound
const int   CH_DEAD_MAX  = 998;     // steering dead-zone upper bound
const float MAX_ANGLE    = 430.0;   // max steering angle (degrees)

const int   CH_THR_MIN   = 990;     // throttle starts above this CH1 value
const int   CH_THR_MAX   = 1811;    // CH1 value at full throttle
const float THROTTLE_LIMIT = 0.5;   // 0.5 = limit output to 50% of DAC range

const int   CH_GEAR_THRESHOLD = 1000; // CH5 below = Drive, at or above = Reverse

const unsigned long SIGNAL_TIMEOUT_MS = 500;  // go safe if no valid frame this long
const uint32_t STEER_CAN_ID = 0x314;

// ---------------- Objects ----------------
Adafruit_MCP4725 dac;
HardwareSerial SBUS_Serial(2);                 // UART2
bfs::SbusRx sbus_rx(&SBUS_Serial, SBUS_RX_PIN, SBUS_TX_PIN, true, false);
bfs::SbusData data;
MCP_CAN CAN(SPI_CS_PIN);

// ---------------- State (last commanded values) ----------------
unsigned long lastValidFrameMs = 0;
float    steeringAngle = 0.0;   // degrees
uint16_t throttleDac   = 0;     // 0..4095
bool     reverseGear   = false; // false = Drive/forward, true = Reverse

// Send all three outputs at once.
void setOutputs(float angleDeg, uint16_t dacValue, bool reverse) {
  // Steering -> CAN (signed int16, 2's complement, big-endian)
  int16_t  angleVal = (int16_t)angleDeg;
  uint16_t canAngle = (angleVal < 0) ? (uint16_t)(65536 + angleVal)
                                     : (uint16_t)angleVal;
  byte angleHigh = (canAngle >> 8) & 0xFF;
  byte angleLow  =  canAngle       & 0xFF;
  byte canData[8] = { 0x01, angleHigh, angleLow, 0x00, 0x00, 0x00, 0x00, 0x00 };
  CAN.sendMsgBuf(STEER_CAN_ID, 0, 8, canData);

  // Throttle -> DAC (false = do not write to EEPROM, fast updates)
  dac.setVoltage(dacValue, false);

  // Gear -> relay. LOW = Drive/forward, HIGH = Reverse.
  // If your relay module is active-LOW or direction is inverted,
  // swap NO/NC wiring or invert this line.
  digitalWrite(RELAY_PIN, reverse ? HIGH : LOW);
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("RC -> CAN steer-by-wire starting...");

  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);     // default: Drive / forward

  // SBUS (Begin configures the UART; no separate Serial.begin needed)
  sbus_rx.Begin();

  // MCP4725 DAC
  Wire.begin(I2C_SDA, I2C_SCL);
  if (!dac.begin(0x60)) {
    Serial.println("MCP4725 not found. Check wiring and address (0x60).");
    while (1) { delay(100); }
  }
  dac.setVoltage(0, false);         // throttle 0 at boot

  // MCP2515 CAN, 8 MHz crystal, 500 kbps
  if (CAN.begin(MCP_ANY, CAN_500KBPS, MCP_8MHZ) == CAN_OK) {
    Serial.println("CAN initialized.");
  } else {
    Serial.println("CAN init FAILED. Check crystal (8 vs 16 MHz) and SPI wiring.");
    while (1) { delay(100); }
  }
  CAN.setMode(MCP_NORMAL);

  Serial.println("System ready.");
}

void loop() {
  bool gotFrame = sbus_rx.Read();
  if (gotFrame) {
    data = sbus_rx.data();
  }

  bool signalLost = data.failsafe ||
                    (millis() - lastValidFrameMs > SIGNAL_TIMEOUT_MS);

  if (gotFrame && !data.failsafe) {
    lastValidFrameMs = millis();

    // ----- CH2: steering -----
    int ch2 = constrain(data.ch[1], CH_RIGHT_END, CH_LEFT_END);
    if (ch2 < CH_DEAD_MIN) {                 // turn right -> negative
      float norm = (float)(CH_DEAD_MIN - ch2) / (float)(CH_DEAD_MIN - CH_RIGHT_END);
      steeringAngle = -constrain(norm, 0.0f, 1.0f) * MAX_ANGLE;
    } else if (ch2 > CH_DEAD_MAX) {          // turn left -> positive
      float norm = (float)(ch2 - CH_DEAD_MAX) / (float)(CH_LEFT_END - CH_DEAD_MAX);
      steeringAngle = constrain(norm, 0.0f, 1.0f) * MAX_ANGLE;
    } else {                                 // dead zone
      steeringAngle = 0.0f;
    }

    // ----- CH1: throttle -----
    int ch1 = data.ch[0];
    if (ch1 > CH_THR_MIN) {
      float ratio = (float)(ch1 - CH_THR_MIN) / (float)(CH_THR_MAX - CH_THR_MIN);
      ratio = constrain(ratio, 0.0f, 1.0f);
      throttleDac = (uint16_t)(ratio * THROTTLE_LIMIT * 4095);
    } else {
      throttleDac = 0;
    }

    // ----- CH5: gear -----
    reverseGear = (data.ch[4] >= CH_GEAR_THRESHOLD);

  } else if (signalLost) {
    // ----- Failsafe / signal loss: center steering, zero throttle, forward -----
    steeringAngle = 0.0f;
    throttleDac   = 0;
    reverseGear   = false;
  }
  // If no new frame but still within the timeout, hold the last values.

  setOutputs(steeringAngle, throttleDac, reverseGear);

  // Debug
  Serial.print("lost="); Serial.print(signalLost);
  Serial.print(" CH1="); Serial.print(data.ch[0]);
  Serial.print(" CH2="); Serial.print(data.ch[1]);
  Serial.print(" angle="); Serial.print(steeringAngle);
  Serial.print(" dac="); Serial.print(throttleDac);
  Serial.print(" gear="); Serial.println(reverseGear ? 'R' : 'D');

  delay(50);  // about 20 Hz
}