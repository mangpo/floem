#include "app.h"
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <queue.h>
#include <cache.h>
#include <jenkins_hash.h>
#include <string.h>
#include <stddef.h>
#include <unistd.h>
#include <pthread.h>
#include <shm.h>
#include <util.h>
#include <arpa/inet.h>
#include <dpdkif.h>

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


#include "protocol_binary.h"

rx_queue_Storage* rx_queue_Storage0;

circular_queue* circular_queue0;

rx_queue_DequeueCollection* rx_queue_DequeueCollection0;

circular_queue* manager_queue;

void init_state_instances(char *argv[]) {
  uintptr_t shm_p = (uintptr_t) util_map_dma();
  uintptr_t shm_start = shm_p;

  rx_queue_Storage* manage_storage = (rx_queue_Storage *) shm_p;
  shm_p = shm_p + MANAGE_SIZE;

  rx_queue_Storage0 = (rx_queue_Storage *) shm_p;
  shm_p = shm_p + sizeof(rx_queue_Storage);
  printf("shared memory size = %ld\n", shm_p - shm_start);
  assert(shm_p - shm_start <= HUGE_PGSIZE);
  memset((void *) shm_start, 0, shm_p - shm_start);

  manager_queue = (circular_queue *) malloc(sizeof(circular_queue));
  memset(manage_storage, 0, MANAGE_SIZE);

  memset(manager_queue, 0, sizeof(circular_queue));
  manager_queue->len = MANAGE_SIZE;
  manager_queue->queue = manage_storage;
  manager_queue->entry_size = sizeof(q_entry_manage);
  manager_queue->n1 = MANAGE_SIZE/sizeof(q_entry_manage)/2;
  manager_queue->n2 = MANAGE_SIZE/sizeof(q_entry_manage) - manager_queue->n1;
  manager_queue->refcount1 = 0;
  manager_queue->refcount2 = 0;
  manager_queue->id = create_dma_circular_queue((uint64_t) manage_storage, MANAGE_SIZE, sizeof(q_entry_manage), enqueue_ready_var, enqueue_done_var);

  circular_queue0 = (circular_queue *) malloc(sizeof(circular_queue));
  rx_queue_DequeueCollection0 = (rx_queue_DequeueCollection *) malloc(sizeof(rx_queue_DequeueCollection));
  memset(rx_queue_Storage0, 0, sizeof(rx_queue_Storage));

  memset(circular_queue0, 0, sizeof(circular_queue));
  circular_queue0->len = 65536;
  circular_queue0->queue = rx_queue_Storage0;
  circular_queue0->entry_size = 64;
  circular_queue0->id = create_dma_circular_queue((uint64_t) rx_queue_Storage0, sizeof(rx_queue_Storage), 64, dequeue_ready_var, dequeue_done_var);
  circular_queue0->n1 = circular_queue0->len/circular_queue0->entry_size/2;
  circular_queue0->n2 = circular_queue0->len/circular_queue0->entry_size - manager_queue->n1;

  memset(rx_queue_DequeueCollection0, 0, sizeof(rx_queue_DequeueCollection));
  rx_queue_DequeueCollection0->insts[0] = circular_queue0;

}

void finalize_state_instances() {}

void main_rx_queue_Dequeue0_get(int);
void main_rx_queue_Dequeue0_classify_inst(q_buffer,int);
void main_run_Display0(pipeline_rx_queue0*);
void rx_queue_save0_inst(q_buffer,int);
void main_rx_queue_Dequeue0_release(q_buffer);
void main_rx_queue_Dequeue0_get(int c) {

            assert(c < 1);
            circular_queue *q = rx_queue_DequeueCollection0->insts[c];
            
#ifdef QUEUE_STAT
    static size_t empty = 0;
    static struct timeval base, now;
    gettimeofday(&now, NULL);
    if(now.tv_sec >= base.tv_sec + 5) {
        printf("\n>>>>>>>>>>>>>>>>>>>>>>>> QUEUE EMPTY[rx_queue]: q = %p, empty/5s = %ld\n", q, empty);
        empty = 0;
        base = now;
    }
#endif
q_buffer buff = dequeue_get((circular_queue*) q);

#ifdef QUEUE_STAT
    if(buff.entry == NULL) empty++;
#endif

                       
  main_rx_queue_Dequeue0_classify_inst(buff, c);
}

void main_rx_queue_Dequeue0_classify_inst(q_buffer buff,  int qid) {

        q_entry* e = buff.entry;
        int type = -1;
        if (e != NULL) type = e->task;
        
  if( (type == 1)) { rx_queue_save0_inst(buff,qid); }
  else if( (type == 0)) { main_rx_queue_Dequeue0_release(buff); }
}

void main_run_Display0(pipeline_rx_queue0* _x0) {
  pipeline_rx_queue0 *_state = _x0;
      
    void *key = _state->entry->key;

    static __thread size_t count = 0;
    static __thread uint64_t lasttime = 0;
    count++;
    if(count == 10000000) {
      struct timeval now;
      gettimeofday(&now, NULL);
      
      uint64_t thistime = now.tv_sec*1000000 + now.tv_usec;
      printf("%zu pkts/s %f Gbits/s\n", (count * 1000000)/(thistime - lasttime), (count * 64 * 8.0)/(thistime - lasttime)/1000);
      lasttime = thistime;
      count = 0;
    }
                
}

void rx_queue_save0_inst(q_buffer buff,  int qid) {
  pipeline_rx_queue0 *_state = (pipeline_rx_queue0 *) malloc(sizeof(pipeline_rx_queue0));
  _state->refcount = 1;  _state->buffer = buff;
  _state->entry = (entry_rx_queue0*) buff.entry;
  
  main_run_Display0(_state);
  main_rx_queue_Dequeue0_release(_state->buffer);
  pipeline_unref((pipeline_state*) _state);
}

void main_rx_queue_Dequeue0_release(q_buffer buf) {

                dequeue_release(buf, 0, manager_queue);
                
}

void init(char *argv[]) {
  init_state_instances(argv);
}

void finalize_and_check() {
  finalize_state_instances();
}


pthread_t _thread_main_rx_queue_Dequeue0_get;
void *_run_main_rx_queue_Dequeue0_get(void *tid) {

        while(true) { main_rx_queue_Dequeue0_get(*((int*) tid)); /* usleep(1000); */ }
        }
int ids_main_rx_queue_Dequeue0_get[1];
void run_threads() {
  ids_main_rx_queue_Dequeue0_get[0] = 0;
  pthread_create(&_thread_main_rx_queue_Dequeue0_get, NULL, _run_main_rx_queue_Dequeue0_get, (void*) &ids_main_rx_queue_Dequeue0_get[0]);
}
void kill_threads() {
  pthread_cancel(_thread_main_rx_queue_Dequeue0_get);
}

