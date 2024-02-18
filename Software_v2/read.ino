#include <SPI.h>
#include <SD.h>
#include "HX711.h"

HX711 scale;
File myFile;

const int LOADCELL_DOUT_PIN = 3;
const int LOADCELL_SCK_PIN = 2;
const int chipSelect = 10; // Pin connected to the CS (chip select) pin of the SD card module
const int misoPin = 12;    // MISO pin of SD card module
const int mosiPin = 11;    // MOSI pin of SD card module
const int sckPin = 13;     // SCK pin of SD card module

String file_name = "test.txt";

void setup(){
  Serial.begin(9600);
  while (!Serial) {
    ;
  }

  pinMode(misoPin, INPUT);
  pinMode(mosiPin, OUTPUT);
  pinMode(sckPin, OUTPUT);
  
  Serial.println("Initializing SD card...");
  if (!SD.begin(chipSelect)) {
    Serial.println("Initialization failed!");
    return;
  }

  Serial.println("Initialization done.");
  scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);

  read_from_file();
}

void write_to_file(long message) {
  myFile = SD.open(file_name, FILE_WRITE);
  if (myFile) {
    Serial.println("Writing to test.txt...");
    myFile.println(message);
    myFile.close();
    Serial.println("Write done.");
  } else {
    Serial.println("Error opening test.txt");
  }
}

void read_from_file(){
  myFile = SD.open(file_name);
  if (myFile) {
    Serial.println(file_name + ":");
    while (myFile.available()) {
      Serial.write(myFile.read());
    }
    myFile.close();
  } else {
    Serial.println("Error opening " + file_name);
  }
}


void loop() {
  ; //ginger
}
