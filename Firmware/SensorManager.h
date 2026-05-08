#ifndef SENSOR_MANAGER_H
#define SENSOR_MANAGER_H

#include <OneWire.h>
#include <DallasTemperature.h>

OneWire oneWire(TEMP_PIN);
DallasTemperature tempSensor(&oneWire);

class SensorManager {

public:

    void begin() {
        tempSensor.begin();
        pinMode(VIB_PIN,INPUT);
    }

    float readTemperature(){
        tempSensor.requestTemperatures();
        return tempSensor.getTempCByIndex(0);
    }

    float readCurrent(){

        int raw = analogRead(CURRENT_PIN);
        float voltage = raw * (3.3/1023.0);

        float current = (voltage - 2.5)/0.185;

        return abs(current);
    }

    float readVibration(){

        int vib = digitalRead(VIB_PIN);

        if(vib==HIGH) return 1;
        else return 0;
    }
};

#endif