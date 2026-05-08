#ifndef RELAY_CONTROLLER_H
#define RELAY_CONTROLLER_H

class RelayController {

private:
    String state="OFF";

public:

    void begin(){
        pinMode(RELAY_PIN,OUTPUT);
        digitalWrite(RELAY_PIN,LOW);
    }

    void setState(String newState){

        state = newState;

        if(state=="ON"){
            digitalWrite(RELAY_PIN,HIGH);
        }
        else{
            digitalWrite(RELAY_PIN,LOW);
        }
    }

    String getState(){
        return state;
    }
};

#endif