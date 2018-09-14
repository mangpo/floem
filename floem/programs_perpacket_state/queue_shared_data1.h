#ifndef QUEUE_SHARED_DATA1_H
#define QUEUE_SHARED_DATA1_H
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <queue.h>
#include <cache.h>
#include <jenkins_hash.h>


typedef struct _MyState { 
int qid;
int* p;
uint8_t* key;
int keylen;
 
} __attribute__ ((packed)) MyState;


typedef struct _queue_Storage { 
uint8_t data[4096];
 
} __attribute__ ((packed)) queue_Storage;


typedef struct _queue_EnqueueCollection { 
circular_queue* insts[2];
 
} __attribute__ ((packed)) queue_EnqueueCollection;


typedef struct _queue_DequeueCollection { 
circular_queue* insts[2];
 
} __attribute__ ((packed)) queue_DequeueCollection;


typedef struct _entry_queue0 { 
uint8_t flag; uint8_t task; uint16_t len; uint8_t checksum; uint8_t pad;  uint64_t p; int keylen; uint8_t _content[];  
} __attribute__ ((packed)) entry_queue0;


typedef struct _pipeline_queue0 { 
int refcount; q_buffer buffer; entry_queue0* entry; int* p; uint8_t* key;  
} __attribute__ ((packed)) pipeline_queue0;


typedef struct _MyState_compressed0 { 
int refcount; int qid;
int* p;
uint8_t* key;
int keylen;
 
} __attribute__ ((packed)) MyState_compressed0;


typedef struct __queue_fill0_from_main_push_Save0_join_buffer { 
q_buffer in_entry_arg0; MyState_compressed0* in_pkt_arg0;  
} __attribute__ ((packed)) _queue_fill0_from_main_push_Save0_join_buffer;

void *data_region;

void push(int arg0, uint8_t arg1);

void init(char *argv[]);
void finalize_and_check();
void run_threads();
void kill_threads();

#endif
