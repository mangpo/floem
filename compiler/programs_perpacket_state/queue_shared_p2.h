#ifndef QUEUE_SHARED_P2_H
#define QUEUE_SHARED_P2_H
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <queue.h>


typedef struct _MyState { 
int core;
int index;
int* p;
 
} __attribute__ ((packed)) MyState;


typedef struct _queue_Storage { 
uint8_t data[4096];
 
} __attribute__ ((packed)) queue_Storage;


typedef struct _queue_EnqueueCollection { 
circular_queue* cores[2];
 
} __attribute__ ((packed)) queue_EnqueueCollection;


typedef struct _queue_DequeueCollection { 
circular_queue* cores[2];
 
} __attribute__ ((packed)) queue_DequeueCollection;


typedef struct _entry_queue0 { 
uint8_t flag; uint8_t task; uint16_t len; uint8_t checksum; uint8_t pad;  uint64_t p; int index;  
} __attribute__ ((packed)) entry_queue0;


typedef struct _pipeline_queue0 { 
int refcount; q_buffer buffer; entry_queue0* entry; int* p;  
} __attribute__ ((packed)) pipeline_queue0;


typedef struct _MyState_compressed0 { 
int refcount; int core;
int index;
int* p;
 
} __attribute__ ((packed)) MyState_compressed0;


typedef struct __queue_fill0_from_main_push_Save0_join_buffer { 
q_buffer in_entry_arg0; MyState_compressed0* in_pkt_arg0;  
} __attribute__ ((packed)) _queue_fill0_from_main_push_Save0_join_buffer;

void *data_region;

void pop(size_t arg0);

void init(char *argv[]);
void finalize_and_check();
void run_threads();
void kill_threads();

#endif
