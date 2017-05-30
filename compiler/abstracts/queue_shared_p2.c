#include "queue_shared_p2.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include <unistd.h>
#include <pthread.h>


#include <rte_memcpy.h>
#include "../queue.h"
#include "../shm.h"

_queue_queue_dummy* _queue_queue_dummy0;

_queue_queue_dummy* _queue_queue_dummy1;

_queue_queue_dummy* _queue_queue_dummy2;

_queue_queue_dummy* _queue_queue_dummy3;

circular_queue* _queue_queue_deq_inst0;

circular_queue* _queue_queue_deq_inst1;

circular_queue* _queue_queue_deq_inst2;

circular_queue* _queue_queue_deq_inst3;

_queue_queues* _queue_queues_deq_inst;

size_t shm_size = 0;
void *shm;
void init_state_instances() {

shm_size += sizeof(_queue_queue_dummy);
shm_size += sizeof(_queue_queue_dummy);
shm_size += sizeof(_queue_queue_dummy);
shm_size += sizeof(_queue_queue_dummy);

shm = util_map_shm("SHARED", shm_size);
uintptr_t shm_p = (uintptr_t) shm;
_queue_queue_dummy0 = (_queue_queue_dummy *) shm_p;
shm_p = shm_p + sizeof(_queue_queue_dummy);

_queue_queue_dummy1 = (_queue_queue_dummy *) shm_p;
shm_p = shm_p + sizeof(_queue_queue_dummy);

_queue_queue_dummy2 = (_queue_queue_dummy *) shm_p;
shm_p = shm_p + sizeof(_queue_queue_dummy);

_queue_queue_dummy3 = (_queue_queue_dummy *) shm_p;
shm_p = shm_p + sizeof(_queue_queue_dummy);

_queue_queue_deq_inst0 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_queue_queue_deq_inst0, 0, sizeof(circular_queue));

_queue_queue_deq_inst0->len = 256;
_queue_queue_deq_inst0->offset = 0;
_queue_queue_deq_inst0->queue = _queue_queue_dummy0;

_queue_queue_deq_inst1 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_queue_queue_deq_inst1, 0, sizeof(circular_queue));

_queue_queue_deq_inst1->len = 256;
_queue_queue_deq_inst1->offset = 0;
_queue_queue_deq_inst1->queue = _queue_queue_dummy1;

_queue_queue_deq_inst2 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_queue_queue_deq_inst2, 0, sizeof(circular_queue));

_queue_queue_deq_inst2->len = 256;
_queue_queue_deq_inst2->offset = 0;
_queue_queue_deq_inst2->queue = _queue_queue_dummy2;

_queue_queue_deq_inst3 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_queue_queue_deq_inst3, 0, sizeof(circular_queue));

_queue_queue_deq_inst3->len = 256;
_queue_queue_deq_inst3->offset = 0;
_queue_queue_deq_inst3->queue = _queue_queue_dummy3;

_queue_queues_deq_inst = (_queue_queues *) malloc(sizeof(_queue_queues));
memset(_queue_queues_deq_inst, 0, sizeof(_queue_queues));

_queue_queues_deq_inst->cores[0] = _queue_queue_deq_inst0;
_queue_queues_deq_inst->cores[1] = _queue_queue_deq_inst1;
_queue_queues_deq_inst->cores[2] = _queue_queue_deq_inst2;
_queue_queues_deq_inst->cores[3] = _queue_queue_deq_inst3;

}

void finalize_state_instances() {

munmap(shm, shm_size);

}

void _queue_smart_deq_ele1_classify_inst(q_entry*,size_t);
void _queue_smart_deq_ele1_release(q_entry*);
void _queue_smart_deq_ele1_get(size_t);
void queue_save0_inst(q_entry*,size_t);
void display(pipeline_queue0*);
void _queue_smart_deq_ele1_classify_inst(q_entry* e,  size_t core) {

        int type = -1;
        if (e != NULL) type = (e->flags & TYPE_MASK) >> TYPE_SHIFT;
        
  if( (type == 1)) { queue_save0_inst(e,core); }
  else if( (type == 0)) { _queue_smart_deq_ele1_release(e); }
}

void _queue_smart_deq_ele1_release(q_entry* eqe) {

        dequeue_release(eqe);
           
}

void _queue_smart_deq_ele1_get(size_t c) {

        circular_queue *q = _queue_queues_deq_inst->cores[c];
        q_entry* x = dequeue_get(q);
                
  _queue_smart_deq_ele1_classify_inst(x, c);
}

void queue_save0_inst(q_entry* e,  size_t core) {
  pipeline_queue0 *_state = (pipeline_queue0 *) malloc(sizeof(pipeline_queue0));_state->entry = (entry_queue0 *) e;
_state->p = (uintptr_t) data_region + (uintptr_t) _state->entry->p;

  display(_state);
}

void display(pipeline_queue0* _x5) {
  pipeline_queue0 *_state = _x5;
    printf("%d\n", _state->p[_state->entry->index]); fflush(stdout);
  _queue_smart_deq_ele1_release((q_entry *) _state->entry);
}

void pop(size_t arg0) { _queue_smart_deq_ele1_get(arg0); }

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

