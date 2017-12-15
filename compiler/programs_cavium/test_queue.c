#include "test_queue.h"
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


int enqueue_ready_struct_tuple(void* buff) {
  struct tuple* dummy = (struct tuple*) buff;
  return (dummy->task == 0)? sizeof(struct tuple): 0;
}
    
int enqueue_done_struct_tuple(void* buff) {
    struct tuple* dummy = (struct tuple*) buff;
    return (dummy->task)? sizeof(struct tuple): 0;
}
        
int dequeue_ready_struct_tuple(void* buff) {
    struct tuple* dummy = (struct tuple*) buff;
    return (dummy->task & FLAG_OWN)? sizeof(struct tuple): 0;
}

int dequeue_done_struct_tuple(void* buff) {
    struct tuple* dummy = (struct tuple*) buff;
    return (dummy->task == 0)? sizeof(struct tuple): 0;
}
        
rx_queue_Storage* rx_queue_Storage0;

circular_queue* circular_queue0;

rx_queue_EnqueueCollection* rx_queue_EnqueueCollection0;

size_t shm_size = 0;
void *shm;
void init_state_instances(char *argv[]) {

shm_size += sizeof(rx_queue_Storage);

shm = util_map_shm("SHARED", shm_size);
uintptr_t shm_p = (uintptr_t) shm;
  rx_queue_Storage0 = (rx_queue_Storage *) shm_p;
  shm_p = shm_p + sizeof(rx_queue_Storage);
  printf("shm_p = %p\n", (void *) shm_p);
  circular_queue0 = (circular_queue *) malloc(sizeof(circular_queue));
  memset(circular_queue0, 0, sizeof(circular_queue));
  circular_queue0->len = 64;
  circular_queue0->queue = rx_queue_Storage0;
  circular_queue0->entry_size = sizeof(struct tuple);
  circular_queue0->id = create_dma_circular_queue((uint64_t) rx_queue_Storage0, sizeof(rx_queue_Storage), sizeof(struct tuple), enqueue_ready_struct_tuple, enqueue_done_struct_tuple);

  rx_queue_EnqueueCollection0 = (rx_queue_EnqueueCollection *) malloc(sizeof(rx_queue_EnqueueCollection));
  memset(rx_queue_EnqueueCollection0, 0, sizeof(rx_queue_EnqueueCollection));
  rx_queue_EnqueueCollection0->insts[0] = circular_queue0;

}
void finalize_state_instances() {

munmap(shm, shm_size);

}

void _nic_rx_FromNetFree0_join_buffer_inp_save(_nic_rx_FromNetFree0_join_buffer *p, void* inp_arg0, void* inp_arg1) {
  p->inp_arg0 = inp_arg0;
  p->inp_arg1 = inp_arg1;
}
void _nic_rx_FromNetFree0_join_buffer__in0_save(_nic_rx_FromNetFree0_join_buffer *p) {
}

void nic_rx_Drop0();
void nic_rx_Enqueue0(_nic_rx_FromNetFree0_join_buffer*,struct tuple*,int);
void nic_rx_FromNetFree0(void*,void*);
void nic_rx_FromNet0();
void nic_rx_FromNet0_out_fork0_inst(size_t,void*,void*);
void nic_rx_DropSize0(_nic_rx_FromNetFree0_join_buffer*,size_t,void*,void*);
void nic_rx_MakeTuple0(_nic_rx_FromNetFree0_join_buffer*,size_t,void*,void*);
void nic_rx_Free0(struct tuple*);
void nic_rx_Drop0() {
  
}

void nic_rx_Enqueue0(_nic_rx_FromNetFree0_join_buffer* _p_nic_rx_FromNetFree0, struct tuple* x,  int c) {

            circular_queue* p = rx_queue_EnqueueCollection0->insts[c];
            rx_queue_Storage* q = p->queue;
            assert(sizeof(q->data[0].task) == 1);
            
    __SYNC;
    size_t old = p->offset;
    size_t new = (old + 1) % 64;
    while(!__sync_bool_compare_and_swap64(&p->offset, old, new)) {
        old = p->offset;
        new = (old + 1) % 64;
    }
    
    
    while(q->data[old].task != 0 || !__sync_bool_compare_and_swap(&q->data[old].task, 0, FLAG_INUSE)) {
        __SYNC;
    }
    
    int type_offset = (uint64_t) &((struct tuple*) 0)->task;
    assert(type_offset > 0);
    assert(p->entry_size - type_offset > 0 && p->entry_size - type_offset <= 64);
    struct tuple* content = &q->data[old];
    memcpy(content, x, type_offset);
    __SYNC;
    
    content->task = FLAG_OWN;
    
    __SYNC;
    
    
  nic_rx_Free0(x);
  _nic_rx_FromNetFree0_join_buffer__in0_save(_p_nic_rx_FromNetFree0);  nic_rx_FromNetFree0(_p_nic_rx_FromNetFree0->inp_arg0, _p_nic_rx_FromNetFree0->inp_arg1);

}

void nic_rx_FromNetFree0(void* p,  void* buf) {

    dpdk_net_free(p, buf);
        
}

void nic_rx_FromNet0() {
  
    static uint32_t count = 0;
    void *data, *buf;
    size_t size;
    dpdk_from_net(&size, &data, &buf, 32);

    
  if( data != NULL) { nic_rx_FromNet0_out_fork0_inst(size, data, buf); }
  else if( data == NULL) { nic_rx_Drop0(); }
}

void nic_rx_FromNet0_out_fork0_inst(size_t _arg0, void* _arg1, void* _arg2) {
  _nic_rx_FromNetFree0_join_buffer *_p_nic_rx_FromNetFree0 = malloc(sizeof(_nic_rx_FromNetFree0_join_buffer));
 
  nic_rx_DropSize0(_p_nic_rx_FromNetFree0,_arg0,_arg1,_arg2);
  nic_rx_MakeTuple0(_p_nic_rx_FromNetFree0,_arg0,_arg1,_arg2);
  free(_p_nic_rx_FromNetFree0);
}

void nic_rx_DropSize0(_nic_rx_FromNetFree0_join_buffer* _p_nic_rx_FromNetFree0, size_t size,  void* pkt,  void* buf) {

        
  _nic_rx_FromNetFree0_join_buffer_inp_save(_p_nic_rx_FromNetFree0, pkt, buf);
}

void nic_rx_MakeTuple0(_nic_rx_FromNetFree0_join_buffer* _p_nic_rx_FromNetFree0, size_t _unused0, void* _unused1, void* _unused2) {
  
  static uint32_t count = 1;
  struct tuple* t = (struct tuple*) malloc(sizeof(struct tuple));

  uint32_t old, new;
  size_t loop = 0;
  do{
    __SYNC;
    old = count;
    new = old + 1;
        loop++;
    if(loop % 1000 == 0) printf("id stuck: count = %ld\n", loop);
    if(loop >= 1000) {
      set_health(12);
    }

    assert(loop < 1000);
  } while(!__sync_bool_compare_and_swap32(&count, old, new));

  t->id = old-1;
  t->task = old;

  int i;
  for(i=0; i<88; i++) t->data[i] = old;
    
  nic_rx_Enqueue0(_p_nic_rx_FromNetFree0,t, 0);
}

void nic_rx_Free0(struct tuple* t) {

    free(t);
        
}

void init(char *argv[]) {
  init_state_instances(argv);
}

void finalize_and_check() {
  finalize_state_instances();
}


pthread_t _thread_nic_rx_FromNet0;
void *_run_nic_rx_FromNet0(void *tid) {

        while(true) { nic_rx_FromNet0(); /* usleep(1000); */ }
        }
int ids_nic_rx_FromNet0[1];
void run_threads() {
  ids_nic_rx_FromNet0[0] = 0;
  pthread_create(&_thread_nic_rx_FromNet0, NULL, _run_nic_rx_FromNet0, (void*) &ids_nic_rx_FromNet0[0]);
}
void kill_threads() {
  pthread_cancel(_thread_nic_rx_FromNet0);
}

