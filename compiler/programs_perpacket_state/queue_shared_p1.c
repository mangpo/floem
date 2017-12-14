#include "queue_shared_p1.h"
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>
#include <unistd.h>
#include <pthread.h>
#include <queue.h>
#include <shm.h>
#include <util.h>
#include <arpa/inet.h>

typedef struct {
    int refcount;
} pipeline_state;

static inline void pipeline_unref(pipeline_state* s) {
    s->refcount--;
    if(s->refcount == 0) {
        free(s);
        //printf("free!\n");
    }
}

static inline void pipeline_ref(pipeline_state* s) {
    s->refcount++;
}

queue_Storage* queue_Storage0;

queue_Storage* queue_Storage1;

circular_queue* circular_queue0;

circular_queue* circular_queue1;

queue_EnqueueCollection* queue_EnqueueCollection0;

size_t shm_size = 0;
void *shm;
void init_state_instances(char *argv[]) {

shm_size += sizeof(queue_Storage);
shm_size += sizeof(queue_Storage);
shm_size += 400;

shm = util_create_shmsiszed("SHARED", shm_size);
uintptr_t shm_p = (uintptr_t) shm;
  data_region = (void *) shm_p;
  shm_p = shm_p + 400;
  queue_Storage1 = (queue_Storage *) shm_p;
  shm_p = shm_p + sizeof(queue_Storage);
  queue_Storage0 = (queue_Storage *) shm_p;
  shm_p = shm_p + sizeof(queue_Storage);
  printf("shm_p = %p\n", (void *) shm_p);
  memset(queue_Storage0, 0, sizeof(queue_Storage));

  memset(queue_Storage1, 0, sizeof(queue_Storage));

  circular_queue0 = (circular_queue *) malloc(sizeof(circular_queue));
  memset(circular_queue0, 0, sizeof(circular_queue));
  circular_queue0->len = 4096;
  circular_queue0->queue = queue_Storage0;
  circular_queue0->entry_size = 32;
  circular_queue0->id = create_dma_circular_queue((uint64_t) queue_Storage0, sizeof(queue_Storage), 32, enqueue_ready_var, enqueue_done_var);

  circular_queue1 = (circular_queue *) malloc(sizeof(circular_queue));
  memset(circular_queue1, 0, sizeof(circular_queue));
  circular_queue1->len = 4096;
  circular_queue1->queue = queue_Storage1;
  circular_queue1->entry_size = 32;
  circular_queue1->id = create_dma_circular_queue((uint64_t) queue_Storage1, sizeof(queue_Storage), 32, enqueue_ready_var, enqueue_done_var);

  queue_EnqueueCollection0 = (queue_EnqueueCollection *) malloc(sizeof(queue_EnqueueCollection));
  memset(queue_EnqueueCollection0, 0, sizeof(queue_EnqueueCollection));
  queue_EnqueueCollection0->cores[0] = circular_queue0;
  queue_EnqueueCollection0->cores[1] = circular_queue1;

}
void finalize_state_instances() {

shm_unlink("SHARED");

munmap(shm, shm_size);

}

void _queue_fill0_from_main_push_Save0_join_buffer_in_entry_save(_queue_fill0_from_main_push_Save0_join_buffer *p, q_buffer in_entry_arg0) {
  p->in_entry_arg0 = in_entry_arg0;
}
void _queue_fill0_from_main_push_Save0_join_buffer_in_pkt_save(_queue_fill0_from_main_push_Save0_join_buffer *p, MyState_compressed0* in_pkt_arg0) {
  p->in_pkt_arg0 = in_pkt_arg0;
}

void main_push_Save0(int);
void queue_size_core0_from_main_push_Save0(_queue_fill0_from_main_push_Save0_join_buffer*,MyState_compressed0*);
void queue_enq_alloc0_from_main_push_Save0(_queue_fill0_from_main_push_Save0_join_buffer*,size_t,size_t,MyState_compressed0*);
void queue_fill0_from_main_push_Save0(q_buffer,MyState_compressed0*);
void queue_fork0_from_main_push_Save0(MyState_compressed0*);
void queue_enq_submit0_from_main_push_Save0(q_buffer);
void main_push_Save0(int _x0) {
  MyState_compressed0 *_state = (MyState_compressed0 *) malloc(sizeof(MyState_compressed0));
  _state->refcount = 1;
    
    _state->index = _x0; _state->p = data_region; _state->core = 0; 
  queue_fork0_from_main_push_Save0(_state);
  pipeline_unref((pipeline_state*) _state);
}

void queue_size_core0_from_main_push_Save0(_queue_fill0_from_main_push_Save0_join_buffer* _p_queue_fill0_from_main_push_Save0, MyState_compressed0* _x1) {
  MyState_compressed0 *_state = _x1;
    
  queue_enq_alloc0_from_main_push_Save0(_p_queue_fill0_from_main_push_Save0,sizeof(entry_queue0), _state->core, _state);
}

void queue_enq_alloc0_from_main_push_Save0(_queue_fill0_from_main_push_Save0_join_buffer* _p_queue_fill0_from_main_push_Save0, size_t len,  size_t c,  MyState_compressed0* _state) {

                        circular_queue *q = queue_EnqueueCollection0->cores[c];
                        q_buffer buff = enqueue_alloc((circular_queue*) q, len, no_clean);

                                                                        
  _queue_fill0_from_main_push_Save0_join_buffer_in_entry_save(_p_queue_fill0_from_main_push_Save0, buff);
}

void queue_fill0_from_main_push_Save0(q_buffer _x2, MyState_compressed0* _x3) {
  MyState_compressed0 *_state = _x3;
      q_buffer buff = _x2;
  entry_queue0* e = (entry_queue0*) buff.entry;
  if(e) {
    e->p = ((uintptr_t) _state->p - (uintptr_t) data_region);
    e->index = (_state->index);
    e->task = 1;
  }  
  queue_enq_submit0_from_main_push_Save0(buff);
}

void queue_fork0_from_main_push_Save0(MyState_compressed0* _x4) {
  _queue_fill0_from_main_push_Save0_join_buffer *_p_queue_fill0_from_main_push_Save0 = malloc(sizeof(_queue_fill0_from_main_push_Save0_join_buffer));
  MyState_compressed0 *_state = _x4;
    
  queue_size_core0_from_main_push_Save0(_p_queue_fill0_from_main_push_Save0,_state);
  _queue_fill0_from_main_push_Save0_join_buffer_in_pkt_save(_p_queue_fill0_from_main_push_Save0, _state);  queue_fill0_from_main_push_Save0(_p_queue_fill0_from_main_push_Save0->in_entry_arg0, _p_queue_fill0_from_main_push_Save0->in_pkt_arg0);

  free(_p_queue_fill0_from_main_push_Save0);
}

void queue_enq_submit0_from_main_push_Save0(q_buffer buf) {

            enqueue_submit(buf, false);
            
}

void push(int arg0) { main_push_Save0(arg0); }

void init(char *argv[]) {
  init_state_instances(argv);
}

void finalize_and_check() {
  finalize_state_instances();
}


void run_threads() {
}
void kill_threads() {
}

