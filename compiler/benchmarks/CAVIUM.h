#ifndef CAVIUM_H
#define CAVIUM_H
#include "cvmcs-nic.h"
#include "floem-queue.h"
#include "floem-cache.h"


#include "protocol_binary.h"


typedef struct _MyState { 
void* pkt_buff;
void* key;
void* pkt;
int qid;
uint16_t keylen;
 
} __attribute__ ((packed)) MyState;


typedef struct _rx_queue_Storage { 
uint8_t data[32768];
 
} __attribute__ ((packed)) rx_queue_Storage;


typedef struct _rx_queue_EnqueueCollection { 
circular_queue* insts[1];
 
} __attribute__ ((packed)) rx_queue_EnqueueCollection;


typedef struct _rx_queue_DequeueCollection { 
circular_queue* insts[1];
 
} __attribute__ ((packed)) rx_queue_DequeueCollection;


typedef struct _entry_rx_queue0 { 
uint8_t flag; uint8_t task; uint16_t len; uint8_t checksum; uint8_t pad;  uint16_t keylen; uint8_t _content[];  
} __attribute__ ((packed)) entry_rx_queue0;


typedef struct _pipeline_rx_queue0 { 
int refcount; q_buffer buffer; entry_rx_queue0* entry; void* key;  
} __attribute__ ((packed)) pipeline_rx_queue0;


typedef struct _MyState_compressed0 { 
int refcount; void* pkt_buff;
void* key;
void* pkt;
int qid;
uint16_t keylen;
 
} __attribute__ ((packed)) MyState_compressed0;


typedef struct __rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer { 
q_buffer in_entry_arg0; MyState_compressed0* in_pkt_arg0;  
} __attribute__ ((packed)) _rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer;


void init(char *argv[]);
void finalize_and_check();
void run_threads();
void kill_threads();
int get_wqe_cond();
void run_from_net(cvmx_wqe_t *wqe);

#endif
