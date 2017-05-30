#include "queue_shared_p1.h"
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

circular_queue* _queue_queue_inst0;

circular_queue* _queue_queue_inst1;

circular_queue* _queue_queue_inst2;

circular_queue* _queue_queue_inst3;

_queue_queues* _queue_queues_inst;

size_t shm_size = 0;
void *shm;
void init_state_instances() {

shm_size += sizeof(_queue_queue_dummy);
shm_size += sizeof(_queue_queue_dummy);
shm_size += sizeof(_queue_queue_dummy);
shm_size += sizeof(_queue_queue_dummy);

shm = util_create_shmsiszed("SHARED", shm_size);
uintptr_t shm_p = (uintptr_t) shm;
_queue_queue_dummy0 = (_queue_queue_dummy *) shm_p;
shm_p = shm_p + sizeof(_queue_queue_dummy);


_queue_queue_dummy1 = (_queue_queue_dummy *) shm_p;
shm_p = shm_p + sizeof(_queue_queue_dummy);


_queue_queue_dummy2 = (_queue_queue_dummy *) shm_p;
shm_p = shm_p + sizeof(_queue_queue_dummy);


_queue_queue_dummy3 = (_queue_queue_dummy *) shm_p;
shm_p = shm_p + sizeof(_queue_queue_dummy);


_queue_queue_inst0 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_queue_queue_inst0, 0, sizeof(circular_queue));

_queue_queue_inst0->len = 256;
_queue_queue_inst0->offset = 0;
_queue_queue_inst0->queue = _queue_queue_dummy0;

_queue_queue_inst1 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_queue_queue_inst1, 0, sizeof(circular_queue));

_queue_queue_inst1->len = 256;
_queue_queue_inst1->offset = 0;
_queue_queue_inst1->queue = _queue_queue_dummy1;

_queue_queue_inst2 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_queue_queue_inst2, 0, sizeof(circular_queue));

_queue_queue_inst2->len = 256;
_queue_queue_inst2->offset = 0;
_queue_queue_inst2->queue = _queue_queue_dummy2;

_queue_queue_inst3 = (circular_queue *) malloc(sizeof(circular_queue));
memset(_queue_queue_inst3, 0, sizeof(circular_queue));

_queue_queue_inst3->len = 256;
_queue_queue_inst3->offset = 0;
_queue_queue_inst3->queue = _queue_queue_dummy3;

_queue_queues_inst = (_queue_queues *) malloc(sizeof(_queue_queues));
memset(_queue_queues_inst, 0, sizeof(_queue_queues));

_queue_queues_inst->cores[0] = _queue_queue_inst0;
_queue_queues_inst->cores[1] = _queue_queue_inst1;
_queue_queues_inst->cores[2] = _queue_queue_inst2;
_queue_queues_inst->cores[3] = _queue_queue_inst3;

}

void finalize_state_instances() {

shm_unlink("SHARED");

munmap(shm, shm_size);

}

void _queue_fill0_from_save_join_buffer_in_entry_save(_queue_fill0_from_save_join_buffer *p, q_entry* in_entry_arg0) {
  p->in_entry_arg0 = in_entry_arg0;
}
void _queue_fill0_from_save_join_buffer_in_pkt_save(_queue_fill0_from_save_join_buffer *p, mystate_compressed0* in_pkt_arg0) {
  p->in_pkt_arg0 = in_pkt_arg0;
}

void queue_enq_alloc0_from_save(_queue_fill0_from_save_join_buffer*,size_t,size_t);
void queue_enq_submit0_from_save(q_entry*);
void queue_fork0_from_save(mystate_compressed0*);
void queue_fill0_from_save(q_entry*,mystate_compressed0*);
void queue_size_core0_from_save(_queue_fill0_from_save_join_buffer*,mystate_compressed0*);
void save(int);
void queue_enq_alloc0_from_save(_queue_fill0_from_save_join_buffer* _p_queue_fill0_from_save, size_t len,  size_t c) {

           circular_queue *q = _queue_queues_inst->cores[c];
                      q_entry* entry = (q_entry*) enqueue_alloc(q, len);
                                 
  _queue_fill0_from_save_join_buffer_in_entry_save(_p_queue_fill0_from_save, entry);
}

void queue_enq_submit0_from_save(q_entry* eqe) {

           enqueue_submit(eqe);
           
}

void queue_fork0_from_save(mystate_compressed0* _x0) {
  _queue_fill0_from_save_join_buffer *_p_queue_fill0_from_save = malloc(sizeof(_queue_fill0_from_save_join_buffer));
  mystate_compressed0 *_state = _x0;
  
  queue_size_core0_from_save(_p_queue_fill0_from_save, _state);
  _queue_fill0_from_save_join_buffer_in_pkt_save(_p_queue_fill0_from_save, _state);  queue_fill0_from_save(_p_queue_fill0_from_save->in_entry_arg0, _p_queue_fill0_from_save->in_pkt_arg0);

}

void queue_fill0_from_save(q_entry* _x1, mystate_compressed0* _x2) {
  mystate_compressed0 *_state = _x2;
  entry_queue0* e = (entry_queue0*) _x1;
e->p = (uintptr_t) _state->p - (uintptr_t) data_region;
e->index = _state->index;
e->flags |= 1 << TYPE_SHIFT;

  queue_enq_submit0_from_save((q_entry*) e);
}

void queue_size_core0_from_save(_queue_fill0_from_save_join_buffer* _p_queue_fill0_from_save, mystate_compressed0* _x3) {
  mystate_compressed0 *_state = _x3;
  
  queue_enq_alloc0_from_save(_p_queue_fill0_from_save, sizeof(entry_queue0), _state->core);
}

void save(int _x4) {
  mystate_compressed0 *_state = (mystate_compressed0 *) malloc(sizeof(mystate_compressed0));
  _state->index = _x4; _state->p = data_region; _state->core = 0; 
  queue_fork0_from_save(_state);
}

void push(int arg0) { save(arg0); }

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

