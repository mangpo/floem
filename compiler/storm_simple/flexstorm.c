#include "flexstorm.h"
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

inject_state* inject_state_inst;

task_master* my_task_master;

queue_state* my_queue_state;

_rx_queue_queue* _rx_queue_queue_inst0;

_rx_queue_queue* _rx_queue_queue_inst1;

_rx_queue_queue* _rx_queue_queue_inst2;

_rx_queue_queue* _rx_queue_queue_inst3;

_rx_queue_queues* _rx_queue_queues_inst;

_tx_queue_queue* _tx_queue_queue_inst0;

_tx_queue_queue* _tx_queue_queue_inst1;

_tx_queue_queue* _tx_queue_queue_inst2;

_tx_queue_queue* _tx_queue_queue_inst3;

_tx_queue_queues* _tx_queue_queues_inst;

size_t shm_size = 0;
void *shm;
void init_state_instances() {

inject_state_inst = (inject_state *) malloc(sizeof(inject_state));
memset(inject_state_inst, 0, sizeof(inject_state));

inject_state_inst->p = 0;

my_task_master = (task_master *) malloc(sizeof(task_master));
memset(my_task_master, 0, sizeof(task_master));

my_task_master->task2executor = get_task2executor();
my_task_master->task2executorid = get_task2executorid();

my_queue_state = (queue_state *) malloc(sizeof(queue_state));
memset(my_queue_state, 0, sizeof(queue_state));

my_queue_state->core = 0;

_rx_queue_queue_inst0 = (_rx_queue_queue *) malloc(sizeof(_rx_queue_queue));
memset(_rx_queue_queue_inst0, 0, sizeof(_rx_queue_queue));

_rx_queue_queue_inst0->head = 0;
_rx_queue_queue_inst0->tail = 0;
_rx_queue_queue_inst0->size = 4096;

_rx_queue_queue_inst1 = (_rx_queue_queue *) malloc(sizeof(_rx_queue_queue));
memset(_rx_queue_queue_inst1, 0, sizeof(_rx_queue_queue));

_rx_queue_queue_inst1->head = 0;
_rx_queue_queue_inst1->tail = 0;
_rx_queue_queue_inst1->size = 4096;

_rx_queue_queue_inst2 = (_rx_queue_queue *) malloc(sizeof(_rx_queue_queue));
memset(_rx_queue_queue_inst2, 0, sizeof(_rx_queue_queue));

_rx_queue_queue_inst2->head = 0;
_rx_queue_queue_inst2->tail = 0;
_rx_queue_queue_inst2->size = 4096;

_rx_queue_queue_inst3 = (_rx_queue_queue *) malloc(sizeof(_rx_queue_queue));
memset(_rx_queue_queue_inst3, 0, sizeof(_rx_queue_queue));

_rx_queue_queue_inst3->head = 0;
_rx_queue_queue_inst3->tail = 0;
_rx_queue_queue_inst3->size = 4096;

_rx_queue_queues_inst = (_rx_queue_queues *) malloc(sizeof(_rx_queue_queues));
memset(_rx_queue_queues_inst, 0, sizeof(_rx_queue_queues));

_rx_queue_queues_inst->cores[0] = _rx_queue_queue_inst0;
_rx_queue_queues_inst->cores[1] = _rx_queue_queue_inst1;
_rx_queue_queues_inst->cores[2] = _rx_queue_queue_inst2;
_rx_queue_queues_inst->cores[3] = _rx_queue_queue_inst3;

_tx_queue_queue_inst0 = (_tx_queue_queue *) malloc(sizeof(_tx_queue_queue));
memset(_tx_queue_queue_inst0, 0, sizeof(_tx_queue_queue));

_tx_queue_queue_inst0->head = 0;
_tx_queue_queue_inst0->tail = 0;
_tx_queue_queue_inst0->size = 4096;

_tx_queue_queue_inst1 = (_tx_queue_queue *) malloc(sizeof(_tx_queue_queue));
memset(_tx_queue_queue_inst1, 0, sizeof(_tx_queue_queue));

_tx_queue_queue_inst1->head = 0;
_tx_queue_queue_inst1->tail = 0;
_tx_queue_queue_inst1->size = 4096;

_tx_queue_queue_inst2 = (_tx_queue_queue *) malloc(sizeof(_tx_queue_queue));
memset(_tx_queue_queue_inst2, 0, sizeof(_tx_queue_queue));

_tx_queue_queue_inst2->head = 0;
_tx_queue_queue_inst2->tail = 0;
_tx_queue_queue_inst2->size = 4096;

_tx_queue_queue_inst3 = (_tx_queue_queue *) malloc(sizeof(_tx_queue_queue));
memset(_tx_queue_queue_inst3, 0, sizeof(_tx_queue_queue));

_tx_queue_queue_inst3->head = 0;
_tx_queue_queue_inst3->tail = 0;
_tx_queue_queue_inst3->size = 4096;

_tx_queue_queues_inst = (_tx_queue_queues *) malloc(sizeof(_tx_queue_queues));
memset(_tx_queue_queues_inst, 0, sizeof(_tx_queue_queues));

_tx_queue_queues_inst->cores[0] = _tx_queue_queue_inst0;
_tx_queue_queues_inst->cores[1] = _tx_queue_queue_inst1;
_tx_queue_queues_inst->cores[2] = _tx_queue_queue_inst2;
_tx_queue_queues_inst->cores[3] = _tx_queue_queue_inst3;

}

void finalize_state_instances() {

}

void __tx_queue_advance_join_buffer_in_save(__tx_queue_advance_join_buffer *p, size_t in_arg0) {
  p->in_arg0 = in_arg0;
}
void __tx_queue_advance_join_buffer__in0_save(__tx_queue_advance_join_buffer *p) {
}

#define _get_struct tuple$(X) X
void queue_schedule();
void inject_inst0();
void _rx_queue_enqueue(struct tuple*,size_t);
void print_tuple_creator0(__tx_queue_advance_join_buffer*,struct tuple*);
void _tx_queue_enqueue(struct tuple*,size_t);
void queue_schedule_out_fork0_inst(size_t);
void _tx_queue_dequeue(__tx_queue_advance_join_buffer*,size_t);
void _rx_queue_advance(size_t);
void _tx_queue_advance(size_t);
void get_core(struct tuple*);
struct tuple* _rx_queue_dequeue(size_t);
void queue_schedule() {
  
    int core = my_queue_state->core;
    my_queue_state->core++;
    
  queue_schedule_out_fork0_inst(core);
}

void inject_inst0() {
  
        if(inject_state_inst->p >= 1000) { printf("Error: inject more than available entries.\n"); exit(-1); }
        int temp = inject_state_inst->p;
        inject_state_inst->p++;
  get_core(inject_state_inst->data[temp]);
}

void _rx_queue_enqueue(struct tuple** x,  size_t c) {

           _rx_queue_queue* p = _rx_queue_queues_inst->cores[c];
           __sync_synchronize();
           int next = p->tail + 1;
           if(next >= p->size) next = 0;
           if(next == p->head) {
             printf("Circular queue 'rx_queue' is full. A packet is dropped.\n");
           } else {
             rte_memcpy(&p->data[p->tail], x, sizeof(struct tuple*));
             p->tail = next;
           }
           __sync_synchronize();
           
}

void print_tuple_creator0(__tx_queue_advance_join_buffer* _p__tx_queue_advance, struct tuple* t) {


      
    printf("TUPLE[0] -- task = %d, fromtask = %d, str = %s, integer = %d\n", t->task, t->fromtask, t->v[0].str, t->v[0].integer);
        fflush(stdout);
                                      
  __tx_queue_advance_join_buffer__in0_save(_p__tx_queue_advance);  _tx_queue_advance(_p__tx_queue_advance->in_arg0);

}

void _tx_queue_enqueue(struct tuple** x,  size_t c) {

           _tx_queue_queue* p = _tx_queue_queues_inst->cores[c];
           __sync_synchronize();
           int next = p->tail + 1;
           if(next >= p->size) next = 0;
           if(next == p->head) {
             printf("Circular queue 'tx_queue' is full. A packet is dropped.\n");
           } else {
             rte_memcpy(&p->data[p->tail], x, sizeof(struct tuple*));
             p->tail = next;
           }
           __sync_synchronize();
           
}

void queue_schedule_out_fork0_inst(size_t _arg0) {
  __tx_queue_advance_join_buffer *_p__tx_queue_advance = malloc(sizeof(__tx_queue_advance_join_buffer));
 
  __tx_queue_advance_join_buffer_in_save(_p__tx_queue_advance, _arg0);
  _tx_queue_dequeue(_p__tx_queue_advance, _arg0);
}

void _tx_queue_dequeue(__tx_queue_advance_join_buffer* _p__tx_queue_advance, size_t c) {

        _tx_queue_queue* p = _tx_queue_queues_inst->cores[c];
           struct tuple** x = NULL;
           bool avail = false;
           if(p->head == p->tail) {
                                     } else {
               avail = true;
               x = &p->data[p->head];
           }
           
  print_tuple_creator0(_p__tx_queue_advance, x);
}

void _rx_queue_advance(size_t c) {

        _rx_queue_queue* p = _rx_queue_queues_inst->cores[c];
        p->head = (p->head + 1) % p->size;
           
}

void _tx_queue_advance(size_t c) {

        _tx_queue_queue* p = _tx_queue_queues_inst->cores[c];
        p->head = (p->head + 1) % p->size;
           
}

void get_core(struct tuple* _x0) {
  
    struct tuple* t = _x0;
    size_t id = my_task_master->task2executorid[t->task];
    
  _rx_queue_enqueue(t, id);
}

struct tuple* _rx_queue_dequeue(size_t c) {

        _rx_queue_queue* p = _rx_queue_queues_inst->cores[c];
           struct tuple** x = NULL;
           bool avail = false;
           if(p->head == p->tail) {
                                     } else {
               avail = true;
               x = &p->data[p->head];
           }
           
  struct tuple* ret;
  ret = _get_struct tuple$(x);
  return ret;
}

void outqueue_put(struct tuple* arg0, size_t arg1) { _tx_queue_enqueue(arg0, arg1); }

void inqueue_advance(size_t arg0) { _rx_queue_advance(arg0); }

struct tuple* inqueue_get(size_t arg0) { return _rx_queue_dequeue(arg0); }

void init() {
  init_memory_regions();
  init_state_instances();
  for(int i = 0; i < 1000; i++) {
    struct tuple* temp = random_tuple(i);
    inject_state_inst->data[i] = temp;
  }
}

void finalize_and_check() {
  finalize_memory_regions();
  finalize_state_instances();
}


pthread_t _thread_inject_inst0;

    void *_run_inject_inst0(void *threadid) {
        usleep(1000);
        for(int i=0; i<1000; i++) {
            //printf("inject = %d\n", i);
            inject_inst0();
            usleep(1000000);
        }
        pthread_exit(NULL);
    }pthread_t _thread_queue_schedule;
void *_run_queue_schedule(void *threadid) { while(true) { queue_schedule(); /* usleep(1000); */ } }
void run_threads() {
  pthread_create(&_thread_inject_inst0, NULL, _run_inject_inst0, NULL);
  pthread_create(&_thread_queue_schedule, NULL, _run_queue_schedule, NULL);
}
void kill_threads() {
  pthread_cancel(_thread_inject_inst0);
  pthread_cancel(_thread_queue_schedule);
}

