#ifndef TMP_H
#define TMP_H
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include <unistd.h>
#include <pthread.h>


#include "worker.h"
#include "storm.h"

void init_memory_regions() {
}
void finalize_memory_regions() {
}

typedef struct _inject_state { struct tuple* data[1000]; int p; } inject_state;
typedef struct _task_master { struct executor **task2executor; } task_master;
size_t shm_size = 0;
void *shm;
void init_state_instances() {

}

void finalize_state_instances() {

}

void init() {
  init_memory_regions();
  init_state_instances();
}

void finalize_and_check() {
  finalize_memory_regions();
  finalize_state_instances();
}


void run_threads() {
}
void kill_threads() {
}

#endif
