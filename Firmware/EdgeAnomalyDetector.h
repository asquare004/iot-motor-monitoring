#ifndef EDGE_ANOMALY_DETECTOR_H
#define EDGE_ANOMALY_DETECTOR_H

#define WINDOW_SIZE 20
#define SIGMA_THRESHOLD 2.5

class EdgeAnomalyDetector {

private:
    float temp_window[WINDOW_SIZE];
    float vib_window[WINDOW_SIZE];
    float current_window[WINDOW_SIZE];

    int temp_index = 0;
    int vib_index = 0;
    int current_index = 0;

    bool windowFilled(float *window) {
        for(int i=0;i<WINDOW_SIZE;i++){
            if(window[i]==0) return false;
        }
        return true;
    }

    float mean(float *window) {
        float sum=0;
        for(int i=0;i<WINDOW_SIZE;i++)
            sum+=window[i];
        return sum/WINDOW_SIZE;
    }

    float stddev(float *window,float mean) {
        float sum=0;
        for(int i=0;i<WINDOW_SIZE;i++){
            float diff = window[i]-mean;
            sum += diff*diff;
        }
        return sqrt(sum/WINDOW_SIZE);
    }

    bool isAnomaly(float value,float *window){

        if(!windowFilled(window)) return false;

        float m = mean(window);
        float s = stddev(window,m);

        if(s==0) return false;

        return abs(value-m) > SIGMA_THRESHOLD*s;
    }

public:

    void updateTemp(float v){
        temp_window[temp_index++ % WINDOW_SIZE] = v;
    }

    void updateVib(float v){
        vib_window[vib_index++ % WINDOW_SIZE] = v;
    }

    void updateCurrent(float v){
        current_window[current_index++ % WINDOW_SIZE] = v;
    }

    bool tempAnomaly(float v){
        return isAnomaly(v,temp_window);
    }

    bool vibAnomaly(float v){
        return isAnomaly(v,vib_window);
    }

    bool currentAnomaly(float v){
        return isAnomaly(v,current_window);
    }
};

#endif