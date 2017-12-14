#include "queue_shared_data2.h"
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

circular_queue* circular_queue2;

circular_queue* circular_queue3;

queue_DequeueCollection* queue_DequeueCollection0;

size_t shm_size = 0;
void *shm;
void init_state_instances(char *argv[]) {

shm_size += sizeof(queue_Storage);
shm_size += sizeof(queue_Storage);
shm_size += 400;

shm = util_map_shm("SHARED", shm_size);
uintptr_t shm_p = (uintptr_t) shm;
  data_region = (void *) shm_p;
  shm_p = shm_p + 400;
  queue_Storage1 = (queue_Storage *) shm_p;
  shm_p = shm_p + sizeof(queue_Storage);
  queue_Storage0 = (queue_Storage *) shm_p;
  shm_p = shm_p + sizeof(queue_Storage);
  printf("shm_p = %p\n", (void *) shm_p);
  circular_queue2 = (circular_queue *) malloc(sizeof(circular_queue));
  memset(circular_queue2, 0, sizeof(circular_queue));
  circular_queue2->len = 4096;
  circular_queue2->queue = queue_Storage0;
  circular_queue2->entry_size = 32;
  circular_queue2->id = create_dma_circular_queue((uint64_t) queue_Storage0, sizeof(queue_Storage), 32, dequeue_ready_var, dequeue_done_var);

  circular_queue3 = (circular_queue *) malloc(sizeof(circular_queue));
  memset(circular_queue3, 0, sizeof(circular_queue));
  circular_queue3->len = 4096;
  circular_queue3->queue = queue_Storage1;
  circular_queue3->entry_size = 32;
  circular_queue3->id = create_dma_circular_queue((uint64_t) queue_Storage1, sizeof(queue_Storage), 32, dequeue_ready_var, dequeue_done_var);

  queue_DequeueCollection0 = (queue_DequeueCollection *) malloc(sizeof(queue_DequeueCollection));
  memset(queue_DequeueCollection0, 0, sizeof(queue_DequeueCollection));
  queue_DequeueCollection0->cores[0] = circular_queue2;
  queue_DequeueCollection0->cores[1] = circular_queue3;

}
void finalize_state_instances() {

munmap(shm, shm_size);

}

void main_pop_queue_Dequeue0_classify_inst(q_buffer,size_t);
void main_pop_queue_Dequeue0_release(q_buffer);
void main_pop_queue_Dequeue0_get(size_t);
void queue_save0_inst(q_buffer,size_t);
void main_pop_Display0(pipeline_queue0*);
void main_pop_queue_Dequeue0_classify_inst(q_buffer buff,  size_t core) {

        q_entry* e = buff.entry;
        int type = -1;
        if (e != NULL) type = e->task;
        
  if( (type == 1)) { queue_save0_inst(buff,core); }
  else if( (type == 0)) { main_pop_queue_Dequeue0_release(buff); }
}

void main_pop_queue_Dequeue0_release(q_buffer buf) {

                            dequeue_release(buf, 0);
                            
}

void main_pop_queue_Dequeue0_get(size_t c) {

                    circular_queue *q = queue_DequeueCollection0->cores[c];
                    
#ifdef QUEUE_STAT
    static size_t empty = 0;
    static struct timeval base, now;
    gettimeofday(&now, NULL);
    if(now.tv_sec >= base.tv_sec + 5) {
        printf("\n>>>>>>>>>>>>>>>>>>>>>>>> QUEUE EMPTY[queue]: q = %p, empty/5s = %ld\n", q, empty);
        empty = 0;
        base = now;
    }
#endif
q_buffer buff = dequeue_get((circular_queue*) q);

#ifdef QUEUE_STAT
    if(buff.entry == NULL) empty++;
#endif

                    
  main_pop_queue_Dequeue0_classify_inst(buff, c);
}

void queue_save0_inst(q_buffer buff,  size_t core) {
  pipeline_queue0 *_state = (pipeline_queue0 *) malloc(sizeof(pipeline_queue0));
  _state->refcount = 1;  _state->buffer = buff;
  _state->entry = (entry_queue0*) buff.entry;
  _state->p = (int*) ((uintptr_t) data_region + (_state->entry->p));
  _state->key = (uint8_t*) _state->entry->key;
  
  main_pop_Display0(_state);
  pipeline_unref((pipeline_state*) _state);
}

void main_pop_Display0(pipeline_queue0* _x4) {
  pipeline_queue0 *_state = _x4;
        
            printf("%d %d %d %d\n", _state->entry->keylen, _state->key[0], _state->key[_state->entry->keylen-1], *_state->p);
            fflush(stdout);
            
  main_pop_queue_Dequeue0_release(_state->buffer);
}

void init(char *argv[]) {
  init_state_instances(argv);
}

void finalize_and_check() {
  finalize_state_instances();
}


pthread_t _thread_main_pop_queue_Dequeue0_get;
void *_run_main_pop_queue_Dequeue0_get(void *tid) {

        while(true) { main_pop_queue_Dequeue0_get(*((int*) tid)); /* usleep(1000); */ }
        }
int ids_main_pop_queue_Dequeue0_get[1];
void run_threads() {
  ids_main_pop_queue_Dequeue0_get[0] = 0;
  pthread_create(&_thread_main_pop_queue_Dequeue0_get, NULL, _run_main_pop_queue_Dequeue0_get, (void*) &ids_main_pop_queue_Dequeue0_get[0]);
}
void kill_threads() {
  pthread_cancel(_thread_main_pop_queue_Dequeue0_get);
}

