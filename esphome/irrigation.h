#include "esphome.h"

// Declare functions before calling them.
bool scheduled_runtime(std::string);
std::string update_next_runtime(std::string);
void irrigation_init();
void start_zone(int zone);
void stop_zone(int zone);
void zone_tick();
void advance_to_next_zone(int completed);

// Zone count
static const int ZONE_COUNT = 20;

// Per-zone state arrays
static float liters_start[ZONE_COUNT] = {0};
static int safety_remaining[ZONE_COUNT] = {0};
static int safety_remaining_prev[ZONE_COUNT] = {0};

// Pointers to ESPHome components
static esphome::template_::TemplateNumber *zone_liters_target[ZONE_COUNT] = {nullptr};
static esphome::template_::TemplateNumber *zone_duration[ZONE_COUNT] = {nullptr};
static esphome::gpio::GPIOSwitch *zone_pin[ZONE_COUNT] = {nullptr};
static esphome::template_::TemplateSensor *zone_remaining_sensor[ZONE_COUNT] = {nullptr};
static esphome::template_::TemplateSensor *zone_liters_remaining_sensor[ZONE_COUNT] = {nullptr};

// Active zone tracker (-1 = idle)
static int active_zone = -1;

bool scheduled_runtime(std::string time) {
  // Retrieve the current time.
  auto time_now = id(sync_time).now();
  int time_hour = time_now.hour;
  int time_minute = time_now.minute;

  // Split the hour and minutes.
  int next_hour = atoi(time.substr(0,2).c_str());
  int next_minute = atoi(time.substr(3,2).c_str());

  return (time_hour == next_hour && time_minute == next_minute);
}

std::string update_next_runtime(std::string time_list) {
  // Initialize variables.
  std::vector<std::string> times;
  std::vector<std::string> next_time;
  char * token;

  // Split the list of run times into an array.
  token = strtok(&time_list[0], ",");
  while (token != NULL) {
    times.push_back(token);
    token = strtok(NULL, ",");
  }

  // Stop now if the list does not contain more than one time.
  if (times.size() <= 1) {
    return time_list;
  }

  // Retrieve the current time.
  auto time_now = id(sync_time).now();
  int time_hour = time_now.hour;
  int time_minute = time_now.minute;

  // Initialize variables.
  int next_hour = 0;
  int next_minute = 0;
  int index = 0;
  int loop_count = 0;
  int time_count = times.size()-1;

  // Compare the list of times with the current time, and return the next in the list.
  for (std::string time : times) {
    // Retrieve the next scheduled time from the list.
    next_hour = atoi(time.substr(0,2).c_str());
    next_minute = atoi(time.substr(3,2).c_str());

    if (time_hour < next_hour || (time_hour == next_hour && time_minute < next_minute)) {
      // Return this time if the next hour is greater than the current hour.
      return times[loop_count].c_str();
      break;
    // When we reach the end of our schedule for the day, return the first time of tomorrow.
    } else if (time_count == loop_count) {
      return times[0].c_str();
      break;
    }

    // Increment the loop counter and array index.
    loop_count += 1;
    index += 2;
  }

  return "unknown";
}

void irrigation_init() {
  zone_duration[0] = id(irrigation_zone0_duration);
  zone_duration[1] = id(irrigation_zone1_duration);
  zone_duration[2] = id(irrigation_zone2_duration);
  zone_duration[3] = id(irrigation_zone3_duration);
  zone_duration[4] = id(irrigation_zone4_duration);
  zone_duration[5] = id(irrigation_zone5_duration);
  zone_duration[6] = id(irrigation_zone6_duration);
  zone_duration[7] = id(irrigation_zone7_duration);
  zone_duration[8] = id(irrigation_zone8_duration);
  zone_duration[9] = id(irrigation_zone9_duration);
  zone_duration[10] = id(irrigation_zone10_duration);
  zone_duration[11] = id(irrigation_zone11_duration);
  zone_duration[12] = id(irrigation_zone12_duration);
  zone_duration[13] = id(irrigation_zone13_duration);
  zone_duration[14] = id(irrigation_zone14_duration);
  zone_duration[15] = id(irrigation_zone15_duration);
  zone_duration[16] = id(irrigation_zone16_duration);
  zone_duration[17] = id(irrigation_zone17_duration);
  zone_duration[18] = id(irrigation_zone18_duration);
  zone_duration[19] = id(irrigation_zone19_duration);

  zone_liters_target[0] = id(irrigation_zone0_liters_target);
  zone_liters_target[1] = id(irrigation_zone1_liters_target);
  zone_liters_target[2] = id(irrigation_zone2_liters_target);
  zone_liters_target[3] = id(irrigation_zone3_liters_target);
  zone_liters_target[4] = id(irrigation_zone4_liters_target);
  zone_liters_target[5] = id(irrigation_zone5_liters_target);
  zone_liters_target[6] = id(irrigation_zone6_liters_target);
  zone_liters_target[7] = id(irrigation_zone7_liters_target);
  zone_liters_target[8] = id(irrigation_zone8_liters_target);
  zone_liters_target[9] = id(irrigation_zone9_liters_target);
  zone_liters_target[10] = id(irrigation_zone10_liters_target);
  zone_liters_target[11] = id(irrigation_zone11_liters_target);
  zone_liters_target[12] = id(irrigation_zone12_liters_target);
  zone_liters_target[13] = id(irrigation_zone13_liters_target);
  zone_liters_target[14] = id(irrigation_zone14_liters_target);
  zone_liters_target[15] = id(irrigation_zone15_liters_target);
  zone_liters_target[16] = id(irrigation_zone16_liters_target);
  zone_liters_target[17] = id(irrigation_zone17_liters_target);
  zone_liters_target[18] = id(irrigation_zone18_liters_target);
  zone_liters_target[19] = id(irrigation_zone19_liters_target);

  zone_pin[0] = id(pin0);
  zone_pin[1] = id(pin1);
  zone_pin[2] = id(pin2);
  zone_pin[3] = id(pin3);
  zone_pin[4] = id(pin4);
  zone_pin[5] = id(pin5);
  zone_pin[6] = id(pin6);
  zone_pin[7] = id(pin7);
  zone_pin[8] = id(pin8);
  zone_pin[9] = id(pin9);
  zone_pin[10] = id(pin10);
  zone_pin[11] = id(pin11);
  zone_pin[12] = id(pin12);
  zone_pin[13] = id(pin13);
  zone_pin[14] = id(pin14);
  zone_pin[15] = id(pin15);
  zone_pin[16] = id(pin16);
  zone_pin[17] = id(pin17);
  zone_pin[18] = id(pin18);
  zone_pin[19] = id(pin19);

  zone_remaining_sensor[0] = id(irrigation_zone0_remaining);
  zone_remaining_sensor[1] = id(irrigation_zone1_remaining);
  zone_remaining_sensor[2] = id(irrigation_zone2_remaining);
  zone_remaining_sensor[3] = id(irrigation_zone3_remaining);
  zone_remaining_sensor[4] = id(irrigation_zone4_remaining);
  zone_remaining_sensor[5] = id(irrigation_zone5_remaining);
  zone_remaining_sensor[6] = id(irrigation_zone6_remaining);
  zone_remaining_sensor[7] = id(irrigation_zone7_remaining);
  zone_remaining_sensor[8] = id(irrigation_zone8_remaining);
  zone_remaining_sensor[9] = id(irrigation_zone9_remaining);
  zone_remaining_sensor[10] = id(irrigation_zone10_remaining);
  zone_remaining_sensor[11] = id(irrigation_zone11_remaining);
  zone_remaining_sensor[12] = id(irrigation_zone12_remaining);
  zone_remaining_sensor[13] = id(irrigation_zone13_remaining);
  zone_remaining_sensor[14] = id(irrigation_zone14_remaining);
  zone_remaining_sensor[15] = id(irrigation_zone15_remaining);
  zone_remaining_sensor[16] = id(irrigation_zone16_remaining);
  zone_remaining_sensor[17] = id(irrigation_zone17_remaining);
  zone_remaining_sensor[18] = id(irrigation_zone18_remaining);
  zone_remaining_sensor[19] = id(irrigation_zone19_remaining);

  zone_liters_remaining_sensor[0] = id(irrigation_zone0_liters_remaining);
  zone_liters_remaining_sensor[1] = id(irrigation_zone1_liters_remaining);
  zone_liters_remaining_sensor[2] = id(irrigation_zone2_liters_remaining);
  zone_liters_remaining_sensor[3] = id(irrigation_zone3_liters_remaining);
  zone_liters_remaining_sensor[4] = id(irrigation_zone4_liters_remaining);
  zone_liters_remaining_sensor[5] = id(irrigation_zone5_liters_remaining);
  zone_liters_remaining_sensor[6] = id(irrigation_zone6_liters_remaining);
  zone_liters_remaining_sensor[7] = id(irrigation_zone7_liters_remaining);
  zone_liters_remaining_sensor[8] = id(irrigation_zone8_liters_remaining);
  zone_liters_remaining_sensor[9] = id(irrigation_zone9_liters_remaining);
  zone_liters_remaining_sensor[10] = id(irrigation_zone10_liters_remaining);
  zone_liters_remaining_sensor[11] = id(irrigation_zone11_liters_remaining);
  zone_liters_remaining_sensor[12] = id(irrigation_zone12_liters_remaining);
  zone_liters_remaining_sensor[13] = id(irrigation_zone13_liters_remaining);
  zone_liters_remaining_sensor[14] = id(irrigation_zone14_liters_remaining);
  zone_liters_remaining_sensor[15] = id(irrigation_zone15_liters_remaining);
  zone_liters_remaining_sensor[16] = id(irrigation_zone16_liters_remaining);
  zone_liters_remaining_sensor[17] = id(irrigation_zone17_liters_remaining);
  zone_liters_remaining_sensor[18] = id(irrigation_zone18_liters_remaining);
  zone_liters_remaining_sensor[19] = id(irrigation_zone19_liters_remaining);

  active_zone = -1;
  ESP_LOGI("irrigation", "Irrigation controller initialized with %d zones", ZONE_COUNT);
}

void start_zone(int zone) {
  if (zone < 0 || zone >= ZONE_COUNT) return;

  active_zone = zone;

  // Snapshot flow total at zone start for liter tracking
  liters_start[zone] = id(flow_total).state;

  // Set safety timer from duration (minutes -> seconds)
  safety_remaining[zone] = (int)(zone_duration[zone]->state * 60);
  safety_remaining_prev[zone] = -1; // force initial publish

  // Publish initial sensor states
  zone_remaining_sensor[zone]->publish_state(zone_duration[zone]->state);

  float target = zone_liters_target[zone]->state;
  zone_liters_remaining_sensor[zone]->publish_state(target);

  // Show "now" on next time display
  id(irrigation_next).publish_state("now");

  ESP_LOGI("irrigation", "Zone %d started: %.1fL target, %ds safety timeout",
           zone, target, safety_remaining[zone]);
}

void stop_zone(int zone) {
  if (zone < 0 || zone >= ZONE_COUNT) return;

  // Zero remaining sensors
  safety_remaining[zone] = 0;
  zone_remaining_sensor[zone]->publish_state(0);
  zone_liters_remaining_sensor[zone]->publish_state(0);

  // Update next scheduled time
  id(irrigation_next).publish_state(
    update_next_runtime(id(irrigation_times).state)
  );

  ESP_LOGI("irrigation", "Zone %d stopped", zone);
}

void advance_to_next_zone(int completed) {
  active_zone = -1;

  // Scan forward from the completed zone for the next enabled zone
  for (int i = completed + 1; i < ZONE_COUNT; i++) {
    float liters = zone_liters_target[i]->state;
    float duration = zone_duration[i]->state;
    if (liters > 0 || duration > 0) {
      // Found an enabled zone — turn on its pin (on_turn_on will call start_zone)
      zone_pin[i]->turn_on();
      return;
    }
  }

  // No more zones to run — cycle complete
  id(irrigation_next).publish_state(
    update_next_runtime(id(irrigation_times).state)
  );
  ESP_LOGI("irrigation", "Watering cycle complete");
}

void zone_tick() {
  if (active_zone < 0 || active_zone >= ZONE_COUNT) return;

  int z = active_zone;

  // Only tick if the pin is actually on
  if (!zone_pin[z]->state) return;

  // Decrement safety timer
  safety_remaining[z] -= 5;
  if (safety_remaining[z] < 0) safety_remaining[z] = 0;

  // Compute liters watered since zone start
  float liters_watered = id(flow_total).state - liters_start[z];
  float liters_target_val = zone_liters_target[z]->state;
  float liters_left = liters_target_val - liters_watered;
  if (liters_left < 0) liters_left = 0;

  // Check completion: liter target reached OR safety timeout
  bool liter_done = (liters_target_val > 0 && liters_watered >= liters_target_val);
  bool timeout = (safety_remaining[z] <= 0);

  if (liter_done || timeout) {
    if (liter_done) {
      ESP_LOGI("irrigation", "Zone %d: liter target reached (%.2f/%.2f L)", z, liters_watered, liters_target_val);
    } else {
      ESP_LOGI("irrigation", "Zone %d: safety timeout expired", z);
    }
    zone_pin[z]->turn_off();
    advance_to_next_zone(z);
    return;
  }

  // Update remaining time display (only on change)
  int remaining_minutes = (safety_remaining[z] / 60) + 1;
  if (safety_remaining_prev[z] != safety_remaining[z]) {
    safety_remaining_prev[z] = safety_remaining[z];
    zone_remaining_sensor[z]->publish_state(remaining_minutes);
  }

  // Update liters remaining display
  zone_liters_remaining_sensor[z]->publish_state(liters_left);
}
