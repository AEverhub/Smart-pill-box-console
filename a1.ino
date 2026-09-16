#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

#define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHARACTERISTIC_RX   "beb5483e-36e1-4688-b7f5-ea07361b26a8"
#define CHARACTERISTIC_TX   "1c95d5e3-d8f7-413a-bf3d-7a2e5d7be87e"

const int CUP_MOTOR_PIN = 25;
const int SLOT_PINS[9]  = {18, 19, 23, 26, 27, 5, 21, 32, 15};

BLEServer* pServer = NULL;
BLECharacteristic* pTxCharacteristic = NULL;
bool deviceConnected = false;
bool deviceEnabled = false;

String alarmTimes[9];

class MyServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
      deviceConnected = true;
    };

    void onDisconnect(BLEServer* pServer) {
      deviceConnected = false;
      pServer->startAdvertising();
    }
};

class MyCallbacks: public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pCharacteristic) {
      String rxValue = pCharacteristic->getValue().c_str();
      rxValue.trim();

      if (rxValue.length() > 0) {
        if (rxValue.startsWith("DEV_ENABLE:")) {
          int state = rxValue.substring(11).toInt();
          deviceEnabled = (state == 1);
        }
        else if (rxValue.startsWith("CUP_CTRL:")) {
          String action = rxValue.substring(9);
          if (action == "LOCK") {
            digitalWrite(CUP_MOTOR_PIN, HIGH);
          } else if (action == "UNLOCK") {
            digitalWrite(CUP_MOTOR_PIN, LOW);
          }
        }
        else if (rxValue.startsWith("SET_ALARMS:")) {
          String timesData = rxValue.substring(11);
          int startIndex = 0;
          for (int i = 0; i < 9; i++) {
            int endIndex = timesData.indexOf(',', startIndex);
            if (endIndex == -1) {
              alarmTimes[i] = timesData.substring(startIndex);
            } else {
              alarmTimes[i] = timesData.substring(startIndex, endIndex);
              startIndex = endIndex + 1;
            }
          }
        }
      }
    }
};

void setup() {
  Serial.begin(115200);

  pinMode(CUP_MOTOR_PIN, OUTPUT);
  digitalWrite(CUP_MOTOR_PIN, HIGH);

  for (int i = 0; i < 9; i++) {
    pinMode(SLOT_PINS[i], INPUT_PULLUP);
  }

  BLEDevice::init("Smart pill box智慧藥盒");
  pServer = BLEDevice::createServer();
  pServer->setCallbacks(new MyServerCallbacks());

  BLEService *pService = pServer->createService(SERVICE_UUID);

  BLECharacteristic *pRxCharacteristic = pService->createCharacteristic(
                                         CHARACTERISTIC_RX,
                                         BLECharacteristic::PROPERTY_WRITE
                                       );
  pRxCharacteristic->setCallbacks(new MyCallbacks());

  pTxCharacteristic = pService->createCharacteristic(
                        CHARACTERISTIC_TX,
                        BLECharacteristic::PROPERTY_NOTIFY
                      );
  pTxCharacteristic->addDescriptor(new BLE2902());

  pService->start();
  pServer->getAdvertising()->start();
}

void loop() {
  if (deviceConnected && deviceEnabled) {
    String slotStatusMsg = "SLOT_STATUS:";
    for (int i = 0; i < 9; i++) {
      int state = digitalRead(SLOT_PINS[i]);
      slotStatusMsg += String(state);
      if (i < 8) slotStatusMsg += ",";
    }
    
    pTxCharacteristic->setValue(slotStatusMsg.c_str());
    pTxCharacteristic->notify();
  }
  
  delay(2000);
}
